import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/presentation/feature_repository.dart';
import 'package:kolovibe/features/account/live_account_repository.dart';
import 'package:kolovibe/features/settings/live_settings_repository.dart';
import 'fl_a_support.dart';

/// Deterministic, obviously synthetic 32-character test input.
String _synthetic(String seed) => seed.padRight(32, 'x');

final fields = <String, String>{
  'Email address': 'mark@example.test',
  'Full name': 'Mark',
  'Display name': 'Mark Updated',
  'Password': _synthetic('typed input'),
  'New password': _synthetic('another input'),
  'Reset code': '482619',
  'verificationCode': '071935'
};
void main() {
  final operations = <UiOperation, String>{
    UiOperation.register: '/auth/register',
    UiOperation.signIn: '/auth/login',
    UiOperation.verifyEmail: '/auth/verify',
    UiOperation.requestCode: '/auth/verification/resend',
    UiOperation.requestReset: '/auth/password/reset-request',
    UiOperation.resetPassword: '/auth/password/reset',
    UiOperation.saveProfile: '/me'
  };
  for (final entry in operations.entries) {
    test('${entry.key} sends the real endpoint and succeeds', () async {
      final fixture = AccountFixture(handler: (request) async {
        expect(request.url.path, '/api/v1${entry.value}');
        expect(request.method,
            entry.key == UiOperation.saveProfile ? 'PATCH' : 'POST');
        expect(request.url.query, isEmpty);
        if (entry.key == UiOperation.signIn) {
          return jsonResponse(
              {'access_token': 'access', 'refresh_token': 'new-refresh'});
        }
        if (entry.key == UiOperation.saveProfile) {
          expect(jsonDecode(request.body), {'display_name': 'Mark Updated'});
        }
        return jsonResponse({});
      });
      final result = await fixture.account
          .executeChecked(UiRequest(entry.key, fields: fields));
      expect(result.available, isTrue);
      if (entry.key == UiOperation.resetPassword) {
        expect(fixture.store.value, isNull);
      }
    });
    for (final status in [400, 401, 403, 409, 429, 503, 0]) {
      test('${entry.key} preserves typed failure $status', () async {
        final fixture = AccountFixture(handler: (request) async {
          if (status == 0) throw http.ClientException('No connection');
          return jsonResponse(
              {'detail': 'Action was not accepted.', 'code': 'test_failure'},
              status);
        });
        await expectLater(
            fixture.account
                .executeChecked(UiRequest(entry.key, fields: fields)),
            throwsA(isA<ApiFailure>()
                .having((e) => e.status, 'status', status == 0 ? 503 : status)
                .having((e) => e.offline, 'offline', status == 0)));
      });
    }
  }
  test('password change requires current password and retains current session',
      () async {
    final fixture = AccountFixture(handler: (request) async {
      expect(request.url.path, '/api/v1/me/password');
      expect(request.method, 'PATCH');
      expect(jsonDecode(request.body), {
        'current_password': fields['Password'],
        'new_password': fields['New password']
      });
      return jsonResponse({});
    });
    await fixture.account.executeChecked(UiRequest(UiOperation.resetPassword,
        fields: {...fields, 'Current password': fields['Password']!}));
    expect(fixture.store.value, 'rotated-refresh');
    expect(await fixture.account.currentAccount(), isNotNull);
  });
  test('password-only MFA response never establishes a session', () async {
    final fixture = AccountFixture(
        credentials: MemoryStore(null),
        handler: (_) async => jsonResponse(
            {'mfa_required': true, 'challenge_token': 'challenge'}));
    await expectLater(
        fixture.account
            .executeChecked(UiRequest(UiOperation.signIn, fields: fields)),
        throwsA(isA<ApiFailure>()));
    expect(fixture.store.value, isNull);
  });
  for (final status in [204, 400, 401, 403, 429, 503, 0]) {
    test('logout clears local credentials even on $status', () async {
      final fixture = AccountFixture(handler: (request) async {
        expect(request.url.path, '/api/v1/auth/logout');
        expect(jsonDecode(request.body), {'refresh_token': 'stored-refresh'});
        if (status == 0) throw http.ClientException('Offline');
        return status == 204
            ? http.Response('', 204)
            : jsonResponse({}, status);
      });
      if (status == 204) {
        await fixture.account.signOut();
      } else {
        await expectLater(
            fixture.account.signOut(), throwsA(isA<ApiFailure>()));
      }
      expect(fixture.store.value, isNull);
    });
  }
  test('cold start restores and rotates a saved session', () async {
    final fixture = AccountFixture();
    expect(
        (await fixture.account.restoreSession())!.email, accountData['email']);
    expect(fixture.store.value, 'rotated-refresh');
    expect(fixture.requests.map((r) => r.url.path),
        ['/api/v1/auth/refresh', '/api/v1/me']);
    final fresh = AccountFixture(credentials: MemoryStore(null));
    expect(await fresh.account.restoreSession(), isNull);
    expect(fresh.requests, isEmpty);
  });
  test('refresh rejection clears session and remains an expired failure',
      () async {
    final store = MemoryStore();
    final account = LiveAccountRepository(
        ApiClient('https://api.example.test/api/v1',
            client: MockClient((_) async => jsonResponse({}, 401))),
        store);
    await expectLater(account.restoreSession(),
        throwsA(isA<ApiFailure>().having((e) => e.status, 'status', 401)));
    expect(store.value, isNull);
  });
  test('reauthentication proof is short lived, one use, never persisted',
      () async {
    final fixture = AccountFixture(handler: (request) async {
      expect(request.url.path, '/api/v1/me/reauthenticate');
      expect(
          jsonDecode(request.body), {'current_password': fields['Password']});
      return jsonResponse(proofData);
    });
    final proof = await fixture.account.reauthenticate(fields['Password']!);
    expect(proof.available, isTrue);
    expect(proof.take(), transientProof);
    expect(proof.available, isFalse);
    expect(proof.take, throwsA(isA<ApiFailure>()));
    expect(fixture.store.value, 'rotated-refresh');
    final expired = Reauthentication(
        transientProof, DateTime.now().subtract(const Duration(seconds: 1)));
    expect(expired.take, throwsA(isA<ApiFailure>()));
  });
  for (final status in [400, 401, 403, 409, 429, 503, 0]) {
    test('reauthentication failure $status stays typed', () async {
      final fixture = AccountFixture(handler: (_) async {
        if (status == 0) throw http.ClientException('Offline');
        return jsonResponse(
            {'detail': 'Identity could not be confirmed.'}, status);
      });
      await expectLater(
          fixture.account.reauthenticate(fields['Password']!),
          throwsA(isA<ApiFailure>()
              .having((e) => e.status, 'status', status == 0 ? 503 : status)));
    });
  }
  for (final kind in ['access', 'deletion']) {
    test('$kind request sends only proof and renders real receipt', () async {
      final fixture = AccountFixture(handler: (request) async {
        if (request.url.path.endsWith('/reauthenticate')) {
          return jsonResponse(proofData);
        }
        expect(jsonDecode(request.body),
            {'kind': kind, 'reauth_token': transientProof});
        return jsonResponse(privacyData(kind), 201);
      });
      final receipt = await LiveSettingsRepository(fixture.account)
          .requestPrivacy(kind, fields['Password']!);
      expect(receipt.id, receiptId);
      expect(receipt.status, 'received');
      expect(
          fixture.requests.any((r) => r.url.path.contains('disable')), isFalse);
    });
    test('$kind duplicate finds existing open receipt, proof cannot be reused',
        () async {
      final fixture = AccountFixture(
          handler: (request) async => request.method == 'POST'
              ? jsonResponse({'code': 'request_open'}, 409)
              : jsonResponse({
                  'items': [privacyData(kind, 'in_review')]
                }));
      final proof = Reauthentication(
          transientProof, DateTime.now().add(const Duration(minutes: 5)));
      final repository = LiveSettingsRepository(fixture.account);
      final receipt = await repository.requestPrivacyWithProof(kind, proof);
      expect(receipt.existing, isTrue);
      expect(receipt.status, 'in_review');
      expect(proof.available, isFalse);
      final count = fixture.requests.length;
      await expectLater(repository.requestPrivacyWithProof(kind, proof),
          throwsA(isA<ApiFailure>()));
      expect(fixture.requests.length, count);
    });
    for (final status in [400, 401, 403, 409, 429, 503, 0]) {
      test('$kind privacy failure $status consumes proof', () async {
        final fixture = AccountFixture(handler: (_) async {
          if (status == 0) throw http.ClientException('Offline');
          return jsonResponse({'detail': 'Unavailable'}, status);
        });
        final proof = Reauthentication(
            transientProof, DateTime.now().add(const Duration(minutes: 5)));
        await expectLater(
            LiveSettingsRepository(fixture.account)
                .requestPrivacyWithProof(kind, proof),
            throwsA(isA<ApiFailure>()));
        expect(proof.available, isFalse);
      });
    }
  }
  for (final status in ['received', 'in_review', 'completed', 'declined']) {
    test('privacy accepts $status without inventing state', () {
      expect(PrivacyReceipt.fromJson(privacyData('access', status)).status,
          status);
    });
  }
}
