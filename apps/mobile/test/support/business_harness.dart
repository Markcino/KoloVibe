import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/security/credential_store.dart';
import 'package:kolovibe/features/account/live_account_repository.dart';
import 'package:kolovibe/features/business/live_business_repository.dart';

const businessId = '00000000-0000-4000-8000-0000000000b1';
const threadId = '00000000-0000-4000-8000-0000000000c1';
const reviewId = '00000000-0000-4000-8000-0000000000d1';
const otherId = '00000000-0000-4000-8000-0000000000e1';

/// A real response captured from the Business service (see the drift test in services/business).
({int status, Map<String, dynamic> body}) fixture(String name) {
  final data =
      jsonDecode(File('test/fixtures/business/$name.json').readAsStringSync())
          as Map<String, dynamic>;
  return (
    status: data['status'] as int,
    body: data['body'] as Map<String, dynamic>
  );
}

class MemoryCredentials implements CredentialStore {
  String? value = 'refresh';
  @override
  Future<void> clearRefreshToken() async => value = null;
  @override
  Future<String?> readRefreshToken() async => value;
  @override
  Future<void> writeRefreshToken(String token) async => value = token;
}

class Recorded {
  Recorded(this.method, this.path, this.query, this.headers, this.body);
  final String method;
  final String path;
  final Map<String, String> query;
  final Map<String, String> headers;
  final Object? body;
}

/// The Business repository over a recording fake gateway. [answer] decides each business reply.
class BusinessHarness {
  BusinessHarness(
      {this.signedIn = true,
      ({int status, Map<String, dynamic> body}) Function(Recorded)? answer})
      : answer = answer ?? ((_) => (status: 503, body: <String, dynamic>{})) {
    final credentials = MemoryCredentials();
    if (!signedIn) credentials.value = null;
    final api = ApiClient('https://api.example.test/api/v1',
        client: MockClient(_handle));
    account = LiveAccountRepository(api, credentials);
    repository = LiveBusinessRepository(api, account);
  }
  final bool signedIn;
  ({int status, Map<String, dynamic> body}) Function(Recorded) answer;
  final List<Recorded> requests = [];
  late final LiveAccountRepository account;
  late final LiveBusinessRepository repository;

  Future<http.Response> _handle(http.Request request) async {
    final path = request.url.path.replaceFirst('/api/v1', '');
    if (path == '/auth/refresh') {
      return http.Response(
          jsonEncode({'access_token': 'access', 'refresh_token': 'rotated'}),
          200);
    }
    if (path == '/me') {
      return http.Response(
          jsonEncode({
            'id': '00000000-0000-4000-8000-000000000001',
            'email': 'a@b.test',
            'display_name': 'Ada',
            'created_at': '2026-11-01T00:00:00Z',
            'roles': ['viewer']
          }),
          200);
    }
    final recorded = Recorded(
        request.method,
        path,
        request.url.queryParameters,
        request.headers,
        request.body.isEmpty ? null : jsonDecode(request.body));
    requests.add(recorded);
    final reply = answer(recorded);
    return http.Response(jsonEncode(reply.body), reply.status);
  }

  Recorded get last => requests.last;
}

/// Replies with one fixture whatever is asked.
({int status, Map<String, dynamic> body}) Function(Recorded) always(
        String name) =>
    (_) => fixture(name);

void expectKey(Recorded request) {
  final key = request.headers['Idempotency-Key'];
  expect(key, isNotNull,
      reason: '${request.method} ${request.path} needs an idempotency key');
  expect(RegExp(r'^[A-Za-z0-9_-]{16,128}$').hasMatch(key!), isTrue);
}
