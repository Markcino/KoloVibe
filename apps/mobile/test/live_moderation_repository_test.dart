import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/security/credential_store.dart';
import 'package:kolovibe/features/account/live_account_repository.dart';
import 'package:kolovibe/features/moderation/live_moderation_repository.dart';

class _Store implements CredentialStore {
  String? token = 'refresh';
  @override
  Future<void> clearRefreshToken() async => token = null;
  @override
  Future<String?> readRefreshToken() async => token;
  @override
  Future<void> writeRefreshToken(String value) async => token = value;
}

void main() {
  test('report uses a stable idempotency key and validates its video',
      () async {
    const video = '00000000-0000-4000-8000-000000000001';
    const report = '00000000-0000-4000-8000-000000000002';
    final key = LiveModerationRepository.newIdempotencyKey();
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
          expect(request.headers['Idempotency-Key'], key);
          expect(request.url.path, '/api/v1/reports');
          expect(jsonDecode(request.body), {
            'video_id': video,
            'reason': 'spam',
            'details': 'Repeated links',
          });
          return http.Response(
              jsonEncode({
                'id': report,
                'video_id': video,
                'status': 'open',
                'created_at': '2026-11-11T12:00:00Z',
              }),
              201);
        })),
        _Store());
    final repository = LiveModerationRepository(account);
    expect(key.length, greaterThanOrEqualTo(16));
    expect(
        (await repository.report(
                videoId: video,
                reason: 'spam',
                details: 'Repeated links',
                key: key))
            .id,
        report);
  });

  test('report rejects invalid reason and mismatched upstream video', () async {
    const video = '00000000-0000-4000-8000-000000000001';
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
          return http.Response(
              jsonEncode({
                'id': '00000000-0000-4000-8000-000000000002',
                'video_id': '00000000-0000-4000-8000-000000000003',
                'status': 'open',
                'created_at': '2026-11-11T12:00:00Z',
              }),
              201);
        })),
        _Store());
    final repository = LiveModerationRepository(account);
    await expectLater(
        repository.report(
            videoId: video,
            reason: 'unsupported',
            details: '',
            key: LiveModerationRepository.newIdempotencyKey()),
        throwsFormatException);
    await expectLater(
        repository.report(
            videoId: video,
            reason: 'spam',
            details: '',
            key: LiveModerationRepository.newIdempotencyKey()),
        throwsFormatException);
  });
}
