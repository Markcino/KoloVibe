import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/security/credential_store.dart';
import 'package:kolovibe/features/account/live_account_repository.dart';
import 'package:kolovibe/features/discovery/live_video_repository.dart';
import 'package:kolovibe/features/discovery/live_video_screen.dart';
import 'package:kolovibe/features/engagement/live_video_engagement_repository.dart';

class _Credentials implements CredentialStore {
  String? token = 'refresh';
  @override
  Future<void> clearRefreshToken() async => token = null;
  @override
  Future<String?> readRefreshToken() async => token;
  @override
  Future<void> writeRefreshToken(String value) async => token = value;
}

class _VideoFixture extends LiveVideoRepository {
  _VideoFixture() : super(ApiClient('https://api.example.test/api/v1'));

  @override
  Future<LiveVideo> detail(String id) async => LiveVideo(
      id, '00000000-0000-4000-8000-000000000003', 'Original', 'Description');
}

class _EngagementFixture extends LiveVideoEngagementRepository {
  _EngagementFixture()
      : super(LiveAccountRepository(
            ApiClient('https://api.example.test/api/v1'), _Credentials()));

  bool liked = false;
  @override
  Future<bool> likeState(String videoId) async => liked;

  @override
  Future<bool> setLiked(String videoId, bool value) async => liked = value;
}

void main() {
  const videoId = '00000000-0000-4000-8000-000000000001';
  const sessionId = '00000000-0000-4000-8000-000000000002';
  final expiry = DateTime.now().toUtc().add(const Duration(minutes: 5));

  test('like state and idempotent toggle use the current account token',
      () async {
    final seen = <String>[];
    final storage = _Credentials();
    final repository = LiveVideoEngagementRepository(LiveAccountRepository(
        ApiClient('https://api.example.test/api/v1',
            client: MockClient((request) async {
          if (request.url.path.endsWith('/auth/refresh')) {
            return http.Response(
                jsonEncode({
                  'access_token': 'access',
                  'refresh_token': 'rotated',
                }),
                200);
          }
          expect(request.headers['Authorization'], 'Bearer access');
          expect(request.url.path, '/api/v1/videos/$videoId/like');
          seen.add(request.method);
          return request.method == 'DELETE'
              ? http.Response('', 204)
              : http.Response(
                  jsonEncode({
                    'video_id': videoId,
                    'liked': request.method == 'PUT',
                    'like_count': request.method == 'PUT' ? 1 : 0,
                  }),
                  200);
        })),
        storage));
    expect(await repository.likeState(videoId), isFalse);
    expect(await repository.setLiked(videoId, true), isTrue);
    expect(await repository.setLiked(videoId, false), isFalse);
    expect(seen, ['GET', 'PUT', 'DELETE']);
    expect(storage.token, 'rotated');
  });

  test('tracked playback grant and progress use account-bound routes',
      () async {
    final seen = <String>[];
    final repository = LiveVideoEngagementRepository(LiveAccountRepository(
        ApiClient('https://api.example.test/api/v1',
            client: MockClient((request) async {
          if (request.url.path.endsWith('/auth/refresh')) {
            return http.Response(
                jsonEncode({
                  'access_token': 'access',
                  'refresh_token': 'rotated',
                }),
                200);
          }
          expect(request.headers['Authorization'], 'Bearer access');
          seen.add('${request.method} ${request.url.path}');
          if (request.url.path.endsWith('/watch-sessions')) {
            return http.Response(
                jsonEncode({
                  'session_id': sessionId,
                  'session_expires_at': expiry.toIso8601String(),
                  'playback_url': 'https://media.example.test/signed/video',
                  'playback_expires_at': expiry.toIso8601String(),
                }),
                200);
          }
          expect(jsonDecode(request.body), {
            'video_id': videoId,
            'session_id': sessionId,
            'position_ms': 3000,
          });
          return http.Response(jsonEncode({'qualified': false}), 200);
        })),
        _Credentials()));
    final grant = await repository.startPlayback(videoId);
    expect(grant.sessionId, sessionId);
    expect(grant.url.host, 'media.example.test');
    expect(await repository.reportProgress(videoId, sessionId, 3000), isFalse);
    expect(seen, [
      'POST /api/v1/videos/$videoId/watch-sessions',
      'POST /api/v1/engagement/watch-events',
    ]);
  });

  test('tracking gate falls back to an ordinary authorized playback grant',
      () async {
    final seen = <String>[];
    final repository = LiveVideoEngagementRepository(LiveAccountRepository(
        ApiClient('https://api.example.test/api/v1',
            client: MockClient((request) async {
          if (request.url.path.endsWith('/auth/refresh')) {
            return http.Response(
                jsonEncode({
                  'access_token': 'access',
                  'refresh_token': 'rotated',
                }),
                200);
          }
          seen.add(request.url.path);
          return request.url.path.endsWith('/watch-sessions')
              ? http.Response(jsonEncode({'detail': 'Unavailable'}), 409)
              : http.Response(
                  jsonEncode({
                    'playback_url': 'https://media.example.test/signed/video',
                    'expires_at': expiry.toIso8601String(),
                  }),
                  200);
        })),
        _Credentials()));
    final grant = await repository.startPlayback(videoId);
    expect(grant.sessionId, isNull);
    expect(seen, [
      '/api/v1/videos/$videoId/watch-sessions',
      '/api/v1/videos/$videoId/playback',
    ]);
  });

  test('expired or insecure playback grants are rejected', () {
    expect(
        () => PlaybackGrant.fromJson({
              'playback_url': 'http://media.example.test/video',
              'expires_at': expiry.toIso8601String(),
            }, tracked: false),
        throwsFormatException);
    expect(
        () => PlaybackGrant.fromJson({
              'playback_url': 'https://media.example.test/video',
              'expires_at': DateTime.now()
                  .subtract(const Duration(seconds: 1))
                  .toIso8601String(),
            }, tracked: false),
        throwsFormatException);
  });

  testWidgets('video detail reads and toggles the account like state',
      (tester) async {
    final engagement = _EngagementFixture();
    await tester.pumpWidget(MaterialApp(
        home: LiveVideoDetailScreen(
            id: videoId, repository: _VideoFixture(), engagement: engagement)));
    await tester.pumpAndSettle();
    expect(find.text('Like'), findsOneWidget);
    await tester.tap(find.text('Like'));
    await tester.pumpAndSettle();
    expect(engagement.liked, isTrue);
    expect(find.text('Unlike'), findsOneWidget);
    expect(find.text('Play original'), findsOneWidget);
  });
}
