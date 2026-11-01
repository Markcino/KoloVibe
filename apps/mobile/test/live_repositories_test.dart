import 'dart:convert';
import 'dart:math';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/presentation/feature_repository.dart';
import 'package:kolovibe/core/security/credential_store.dart';
import 'package:kolovibe/features/account/live_account_repository.dart';
import 'package:kolovibe/features/discovery/live_video_repository.dart';
import 'package:kolovibe/features/creators/live_creator_repository.dart';

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
  test('expired access refreshes once and concurrent reads share rotation',
      () async {
    final storage = MemoryCredentials()..value = 'initial-refresh';
    var rotations = 0;
    var expire = false;
    final api = ApiClient('https://api.example.test/api/v1',
        client: MockClient((request) async {
      if (request.url.path.endsWith('/refresh')) {
        rotations++;
        expect(jsonDecode(request.body)['refresh_token'],
            rotations == 1 ? 'initial-refresh' : 'refresh-1');
        return http.Response(
            jsonEncode({
              'access_token': 'access-$rotations',
              'refresh_token': 'refresh-$rotations',
            }),
            200);
      }
      if (expire && request.headers['Authorization'] == 'Bearer access-1') {
        return http.Response('{}', 401);
      }
      return http.Response(
          jsonEncode({
            'id': 'account',
            'email': 'user@example.test',
            'display_name': 'Viewer',
            'roles': ['viewer'],
          }),
          200);
    }));
    final repository = LiveAccountRepository(api, storage);
    expect(await repository.currentAccount(), isNotNull);
    expire = true;
    final accounts = await Future.wait([
      repository.currentAccount(),
      repository.currentAccount(),
    ]);
    expect(accounts.every((account) => account != null), isTrue);
    expect(rotations, 2);
    expect(storage.value, 'refresh-2');
  });

  test('transient refresh failure preserves credentials; rejection clears them',
      () async {
    final storage = MemoryCredentials()..value = 'current-refresh';
    var status = 503;
    final api = ApiClient('https://api.example.test/api/v1',
        client: MockClient((_) async => http.Response('{}', status)));
    final repository = LiveAccountRepository(api, storage);
    await expectLater(repository.currentAccount(), throwsA(isA<ApiFailure>()));
    expect(storage.value, 'current-refresh');
    status = 401;
    expect(await repository.currentAccount(), isNull);
    expect(storage.value, isNull);
  });

  test(
      'logout outage clears device credentials but reports unconfirmed revocation',
      () async {
    final storage = MemoryCredentials()..value = 'current-refresh';
    final api = ApiClient('https://api.example.test/api/v1',
        client: MockClient((_) async => http.Response('{}', 503)));
    final result = await LiveAccountRepository(api, storage)
        .execute(const UiRequest(UiOperation.signOut));
    expect(result.available, isFalse);
    expect(result.message, contains('could not be confirmed'));
    expect(storage.value, isNull);
  });

  test('live discovery accepts only published typed records', () async {
    final api = ApiClient('https://api.example.test/api/v1',
        client: MockClient((request) async {
      expect(request.url.path, '/api/v1/videos');
      return http.Response(
          jsonEncode({
            'items': [
              {
                'id': '00000000-0000-4000-8000-000000000001',
                'creator_id': '00000000-0000-4000-8000-000000000002',
                'title': 'A real original',
                'description': '',
                'state': 'published'
              }
            ],
            'next_cursor': null
          }),
          200);
    }));
    final videos = await LiveVideoRepository(api).list();
    expect(videos.single.title, 'A real original');
  });

  test('creator detail accepts only an active matching profile', () async {
    const id = '00000000-0000-4000-8000-000000000003';
    final api = ApiClient('https://api.example.test/api/v1',
        client: MockClient((request) async {
      expect(request.url.path, '/api/v1/creators/$id');
      return http.Response(
          jsonEncode({
            'id': id,
            'user_id': '00000000-0000-4000-8000-000000000004',
            'handle': 'original-voice',
            'bio': '',
            'status': 'active'
          }),
          200);
    }));
    expect(
        (await LiveCreatorRepository(api).detail(id)).handle, 'original-voice');
  });

  test('video pagination sends cursor and rejects repeated cursor', () async {
    final ids = List.generate(
        20,
        (index) =>
            '00000000-0000-4000-8000-${index.toString().padLeft(12, '0')}');
    final api = ApiClient('https://api.example.test/api/v1',
        client: MockClient((request) async {
      final cursor = request.url.queryParameters['cursor'];
      if (cursor != null) expect(cursor, ids.last);
      return http.Response(
          jsonEncode({
            'items': ids
                .map((id) => {
                      'id': id,
                      'creator_id': '00000000-0000-4000-8000-000000000099',
                      'title': 'Original',
                      'description': '',
                      'state': 'published',
                    })
                .toList(),
            'next_cursor': ids.last,
          }),
          200);
    }));
    final repository = LiveVideoRepository(api);
    expect((await repository.page()).nextCursor, ids.last);
    await expectLater(repository.page(cursor: ids.last), throwsFormatException);
    await expectLater(repository.detail('../me'), throwsFormatException);
  });

  test('identity keeps access token in memory and clears refresh on sign-out',
      () async {
    final storage = MemoryCredentials();
    final calls = <String>[];
    final api = ApiClient('https://api.example.test/api/v1',
        client: MockClient((request) async {
      calls.add(request.url.path);
      if (request.url.path.endsWith('/login')) {
        return http.Response(
            jsonEncode({'access_token': 'access', 'refresh_token': 'refresh'}),
            200);
      }
      if (request.url.path.endsWith('/logout')) {
        expect(jsonDecode(request.body), {'refresh_token': 'refresh'});
        return http.Response('', 204);
      }
      return http.Response('{}', 503);
    }));
    final repo = LiveAccountRepository(api, storage);
    final entered =
        List.generate(24, (_) => Random.secure().nextInt(10)).join();
    final login = await repo.execute(UiRequest(UiOperation.signIn,
        fields: {'Email address': 'user@example.test', 'Password': entered}));
    expect(login.available, isTrue);
    expect(storage.value, 'refresh');
    await repo.execute(const UiRequest(UiOperation.signOut));
    expect(storage.value, isNull);
    expect(calls, ['/api/v1/auth/login', '/api/v1/auth/logout']);
  });

  test('redirects are rejected before credentials leave the gateway origin',
      () async {
    final api = ApiClient('https://api.example.test/api/v1',
        client: MockClient((request) async {
      expect(request.followRedirects, isFalse);
      return http.Response('{}', 302,
          headers: {'location': 'https://other.example.test'});
    }));
    expect(() => api.request('/me', accessToken: 'ephemeral'),
        throwsA(isA<ApiFailure>()));
  });
}
