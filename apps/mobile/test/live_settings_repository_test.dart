import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/security/credential_store.dart';
import 'package:kolovibe/features/account/live_account_repository.dart';
import 'package:kolovibe/features/settings/live_settings_repository.dart';

class _Credentials implements CredentialStore {
  String? value = 'local-refresh';
  @override
  Future<void> clearRefreshToken() async => value = null;
  @override
  Future<String?> readRefreshToken() async => value;
  @override
  Future<void> writeRefreshToken(String token) async => value = token;
}

void main() {
  test('preferences and privacy receipts use bearer and own account routes', () async {
    final store = _Credentials();
    final entered = 'test input'.padRight(32, 'x');
    var requests = 0;
    final api = ApiClient('https://api.example.test/api/v1',
        client: MockClient((request) async {
      if (request.url.path.endsWith('/auth/refresh')) {
        return http.Response(jsonEncode({
          'access_token': 'access', 'refresh_token': 'rotated-refresh',
        }), 200);
      }
      requests++;
      expect(request.headers['Authorization'], 'Bearer access');
      if (request.url.path.endsWith('/me/preferences')) {
        if (request.method == 'PATCH') {
          expect(jsonDecode(request.body), {
            'email_notifications': true, 'push_notifications': false,
          });
          return http.Response(request.body, 200);
        }
        return http.Response(jsonEncode({
          'email_notifications': false, 'push_notifications': false,
        }), 200);
      }
      expect(request.url.path, '/api/v1/me/privacy-requests');
      if (request.method == 'POST') {
        expect(jsonDecode(request.body), {
          'kind': 'deletion', 'current_password': entered,
        });
        return http.Response(jsonEncode({
          'id': '00000000-0000-4000-8000-000000000001',
          'kind': 'deletion', 'status': 'received',
          'created_at': '2026-11-11T12:00:00Z',
        }), 201);
      }
      return http.Response('{"items":[]}', 200);
    }));
    final repository = LiveSettingsRepository(LiveAccountRepository(api, store));
    expect((await repository.preferences()).email, isFalse);
    expect((await repository.updatePreferences(
        const NotificationChoices(true, false))).email, isTrue);
    expect((await repository.privacyRequests()), isEmpty);
    expect((await repository.requestPrivacy('deletion', entered)).status,
        'received');
    expect(store.value, 'rotated-refresh');
    expect(requests, 4);
  });

  test('invalid receipt and notification payloads fail closed', () async {
    final account = LiveAccountRepository(ApiClient('https://api.example.test/api/v1',
      client: MockClient((request) async {
        if (request.url.path.endsWith('/auth/refresh')) {
          return http.Response(jsonEncode({
            'access_token': 'access', 'refresh_token': 'rotated',
          }), 200);
        }
        if (request.url.path.endsWith('/me/preferences')) {
          return http.Response('{"email_notifications":1,"push_notifications":false}', 200);
        }
        return http.Response('{"items":[{"id":"bad","kind":"deletion","status":"received","created_at":"2026-11-11T12:00:00Z"}]}', 200);
      })), _Credentials());
    final repository = LiveSettingsRepository(account);
    await expectLater(repository.preferences(), throwsFormatException);
    await expectLater(repository.privacyRequests(), throwsFormatException);
    await expectLater(repository.requestPrivacy('deletion', ''), throwsFormatException);
  });
}
