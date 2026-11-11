import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/security/credential_store.dart';
import 'package:kolovibe/features/account/live_account_repository.dart';
import 'package:kolovibe/features/content/live_content_repository.dart';
import 'package:kolovibe/features/creators/live_creator_onboarding_repository.dart';

class _Credentials implements CredentialStore {
  String? value = 'refresh';
  @override
  Future<void> clearRefreshToken() async => value = null;
  @override
  Future<String?> readRefreshToken() async => value;
  @override
  Future<void> writeRefreshToken(String token) async => value = token;
}

void main() {
  const accountId = '00000000-0000-4000-8000-000000000001';
  const creatorId = '00000000-0000-4000-8000-000000000002';
  const videoId = '00000000-0000-4000-8000-000000000003';
  const uploadId = '00000000-0000-4000-8000-000000000004';
  const key = 'a-unique-upload-key-1234';
  final expiry = DateTime.now().toUtc().add(const Duration(minutes: 5));

  test('creator invitation and eligibility use the current account', () async {
    var applicationStatus = 'invited';
    final account = LiveAccountRepository(
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
          if (request.url.path.endsWith('/upload-eligibility')) {
            return http.Response(
                jsonEncode({
                  'upload_eligible': false,
                  'creator_id': null,
                }),
                200);
          }
          expect(request.url.path, '/api/v1/creators/me/application');
          if (request.method == 'POST') {
            expect(jsonDecode(request.body), {
              'handle': 'Storyteller',
              'adult_attested': true,
              'rights_attested': true,
            });
            applicationStatus = 'pending';
          }
          return http.Response(
              jsonEncode({
                'account_id': accountId,
                'status': applicationStatus,
                'creator_id': null,
              }),
              200);
        })),
        _Credentials());
    final repository = LiveCreatorOnboardingRepository(account);
    expect((await repository.eligibility()).eligible, isFalse);
    expect((await repository.application())!.status, 'invited');
    await expectLater(
        repository.submit(
            handle: 'Storyteller',
            adultAttested: false,
            rightsAttested: true),
        throwsFormatException);
    expect(
        (await repository.submit(
                handle: ' Storyteller ',
                adultAttested: true,
                rightsAttested: true))
            .status,
        'pending');
  });

  test('draft, signed upload, and completion use validated grants', () async {
    final gateway = MockClient((request) async {
      if (request.url.path.endsWith('/auth/refresh')) {
        return http.Response(
            jsonEncode({
              'access_token': 'access',
              'refresh_token': 'rotated',
            }),
            200);
      }
      expect(request.headers['Authorization'], 'Bearer access');
      if (request.url.path == '/api/v1/videos') {
        expect(request.headers['Idempotency-Key'], key);
        expect(jsonDecode(request.body), {
          'title': 'My original',
          'description': 'A story',
        });
        return http.Response(
            jsonEncode({
              'id': videoId,
              'creator_id': creatorId,
              'title': 'My original',
              'description': 'A story',
              'state': 'draft',
              'created_at': '2026-11-11T10:00:00Z',
            }),
            201);
      }
      if (request.url.path.endsWith('/upload-intents')) {
        expect(request.headers['Idempotency-Key'], key);
        expect(jsonDecode(request.body), {'size_bytes': 12});
        return http.Response(
            jsonEncode({
              'video_id': videoId,
              'upload_id': uploadId,
              'upload_url': 'https://media.example.test/upload?signature=opaque',
              'upload_headers': {
                'Content-Type': 'video/mp4',
                'Content-Length': '12',
                'If-None-Match': '*',
              },
              'expires_at': expiry.toIso8601String(),
              'max_bytes': 50 * 1024 * 1024,
            }),
            200);
      }
      expect(request.url.path, '/api/v1/videos/$videoId/upload-status');
      return http.Response(
          jsonEncode({'video_id': videoId, 'state': 'processing'}), 202);
    });
    final media = MockClient((request) async {
      expect(request.method, 'PUT');
      expect(request.url.queryParameters['signature'], 'opaque');
      expect(request.followRedirects, isFalse);
      expect(request.headers['Content-Type'], 'video/mp4');
      expect(request.headers['If-None-Match'], '*');
      expect(request.bodyBytes.length, 12);
      return http.Response('', 201);
    });
    final account = LiveAccountRepository(
        ApiClient('https://api.example.test/api/v1', client: gateway),
        _Credentials());
    final repository = LiveContentRepository(account, uploadClient: media);
    final draft = await repository.createDraft(
        title: ' My original ', description: 'A story', idempotencyKey: key);
    final intent = await repository.reserveUpload(draft, 12, key);
    await repository.uploadToProvider(intent,
        Stream.value([0, 0, 0, 12, 0x66, 0x74, 0x79, 0x70, 0, 0, 0, 0]), 12);
    expect((await repository.completeUpload(draft.id)).state, 'processing');
  });

  test('upload grant rejects insecure host and mismatched content length', () {
    final data = {
      'video_id': videoId,
      'upload_id': uploadId,
      'upload_url': 'http://media.example.test/upload',
      'upload_headers': {
        'Content-Type': 'video/mp4',
        'Content-Length': '11',
        'If-None-Match': '*',
      },
      'expires_at': expiry.toIso8601String(),
      'max_bytes': 50 * 1024 * 1024,
    };
    expect(() => UploadIntent.fromJson(data, videoId, 12),
        throwsFormatException);
    expect(
        () => UploadIntent.fromJson(
            {...data, 'upload_url': 'https://media.example.test/upload'},
            videoId,
            12),
        throwsFormatException);
  });
}
