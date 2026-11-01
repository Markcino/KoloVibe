import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/presentation/feature_repository.dart';
import 'package:kolovibe/core/security/credential_store.dart';
import 'package:kolovibe/features/account/live_account_repository.dart';
import 'package:kolovibe/features/discovery/live_video_repository.dart';

class MemoryCredentials implements CredentialStore {
  String? value;
  @override
  Future<void> clearRefreshToken() async => value = null;
  @override
  Future<String?> readRefreshToken() async => value;
  @override
  Future<void> writeRefreshToken(String token) async => value = token;
}

void main() {
  test('live discovery accepts only published typed records', () async {
    final api = ApiClient('https://api.example.test/api/v1', client: MockClient((request) async {
      expect(request.url.path, '/api/v1/videos');
      return http.Response(jsonEncode({'items': [
        {'id': '00000000-0000-4000-8000-000000000001',
         'creator_id': '00000000-0000-4000-8000-000000000002',
         'title': 'A real original', 'description': '', 'state': 'published'}
      ]}), 200);
    }));
    final videos = await LiveVideoRepository(api).list();
    expect(videos.single.title, 'A real original');
  });

  test('identity keeps access token in memory and clears refresh on sign-out', () async {
    final storage = MemoryCredentials();
    final calls = <String>[];
    final api = ApiClient('https://api.example.test/api/v1', client: MockClient((request) async {
      calls.add(request.url.path);
      if (request.url.path.endsWith('/login')) {
        return http.Response(jsonEncode({'access_token': 'access', 'refresh_token': 'refresh'}), 200);
      }
      if (request.url.path.endsWith('/logout')) {
        expect(jsonDecode(request.body), {'refresh_token': 'refresh'});
        return http.Response('', 204);
      }
      return http.Response('{}', 503);
    }));
    final repo = LiveAccountRepository(api, storage);
    final login = await repo.execute(const UiRequest(UiOperation.signIn,
        fields: {'Email address': 'user@example.test', 'Password': 'entered-at-runtime'}));
    expect(login.available, isTrue);
    expect(storage.value, 'refresh');
    await repo.execute(const UiRequest(UiOperation.signOut));
    expect(storage.value, isNull);
    expect(calls, ['/api/v1/auth/login', '/api/v1/auth/logout']);
  });

  test('redirects are rejected before credentials leave the gateway origin', () async {
    final api = ApiClient('https://api.example.test/api/v1', client: MockClient((request) async {
      expect(request.followRedirects, isFalse);
      return http.Response('{}', 302, headers: {'location': 'https://other.example.test'});
    }));
    expect(() => api.request('/me', accessToken: 'ephemeral'),
        throwsA(isA<ApiFailure>()));
  });
}
