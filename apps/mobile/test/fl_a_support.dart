import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/platform/device_bridge.dart';
import 'package:kolovibe/core/security/credential_store.dart';
import 'package:kolovibe/features/account/live_account_repository.dart';

const accountId = '00000000-0000-4000-8000-000000000001';
const receiptId = '00000000-0000-4000-8000-000000000002';
final accountData = <String, Object?>{
  'id': accountId,
  'email': 'mark@example.test',
  'display_name': 'Mark',
  'roles': ['user', 'creator']
};
Map<String, Object?> privacyData(String kind, [String status = 'received']) => {
      'id': receiptId,
      'kind': kind,
      'status': status,
      'created_at': '2026-11-11T12:00:00Z'
    };
String get transientProof => List.filled(40, 'p').join();
Map<String, Object?> get proofData => {
      'reauth_token': transientProof,
      'expires_at': DateTime.now()
          .toUtc()
          .add(const Duration(minutes: 5))
          .toIso8601String()
    };
http.Response jsonResponse(Object? value, [int status = 200]) =>
    http.Response(jsonEncode(value), status);

class MemoryStore implements CredentialStore {
  MemoryStore([this.value = 'stored-refresh']);
  String? value;
  @override
  Future<String?> readRefreshToken() async => value;
  @override
  Future<void> writeRefreshToken(String token) async => value = token;
  @override
  Future<void> clearRefreshToken() async => value = null;
}

class TestDevice extends DeviceBridge {
  AppVersion? version = const AppVersion('1.2.3', '12');
  bool opens = true;
  int settingsCalls = 0;
  final urls = <Uri>[];
  @override
  Future<AppVersion?> appVersion() async => version;
  @override
  Future<bool> openAppSettings() async {
    settingsCalls++;
    return opens;
  }

  @override
  Future<bool> openUrl(Uri url) async {
    urls.add(url);
    return opens;
  }

  @override
  Future<bool> share(String text) async => false;
}

class AccountFixture {
  AccountFixture({this.handler, MemoryStore? credentials})
      : store = credentials ?? MemoryStore() {
    client = MockClient((request) async {
      requests.add(request);
      if (request.url.path.endsWith('/auth/refresh')) {
        return jsonResponse(
            {'access_token': 'access', 'refresh_token': 'rotated-refresh'});
      }
      if (request.url.path.endsWith('/me') && request.method == 'GET') {
        return jsonResponse(accountData);
      }
      return handler?.call(request) ?? jsonResponse({});
    });
    account = LiveAccountRepository(
        ApiClient('https://api.example.test/api/v1', client: client), store);
  }
  final Future<http.Response> Function(http.Request)? handler;
  final MemoryStore store;
  late final http.Client client;
  late final LiveAccountRepository account;
  final requests = <http.Request>[];
}

/// Decision B: a current legal text as the Gateway serves it (shape checked by the Gateway tests and the journey).
Map<String, Object?> legalDocument(String kind, {String version = '2026-11-25'}) => {
      'kind': kind,
      'title': {'terms': 'Terms of Service', 'privacy': 'Privacy Notice', 'marketing': 'Marketing messages'}[kind],
      'version': version,
      'effective_at': '2026-11-25',
      'status': 'pending_legal_review',
      'sha256': 'a' * 64,
      'text': '# Title\n\n**DRAFT. PENDING LEGAL REVIEW.**\n\n## Section\n\n- one item\n',
    };

/// Decision B: the signed-in acceptance state.
Map<String, Object?> legalState({bool required = false, bool marketing = false, String version = '2026-11-25'}) => {
      'documents': [
        for (final kind in ['terms', 'privacy'])
          {
            ...legalDocument(kind, version: version)..remove('text'),
            'accepted_version': required ? null : version,
            'accepted_at': required ? null : '2026-11-25T10:00:00+00:00',
          }
      ],
      'acceptance_required': required,
      'marketing': {'granted': marketing, 'version': '2026-11-25', 'updated_at': null},
    };
