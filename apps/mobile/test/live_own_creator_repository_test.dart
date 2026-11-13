import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/features/account/live_account_repository.dart';
import 'package:kolovibe/features/creators/live_creator_onboarding_repository.dart';
import 'package:kolovibe/features/creators/live_own_creator_repository.dart';

import 'support/upload_fakes.dart';

/// Repository contract tests with mocked HTTP (`MockClient`): the requests
/// and DOC-205 `OwnCreator` / `CreatorUpdate` shapes are asserted, but no
/// gateway, network or device is involved.
void main() {
  Map<String, Object?> profileJson({
    String handle = 'amakollie',
    String name = 'Ama Kollie',
    String bio = 'Finding the cinema.',
    String location = 'Monrovia',
    Map<String, Object?> extra = const {},
    String status = 'active',
  }) =>
      {
        'id': creatorId,
        'user_id': accountId,
        'handle': handle,
        'display_name': name,
        'bio': bio,
        'location': location,
        'status': status,
        ...extra,
      };

  late List<http.Request> requests;

  LiveOwnCreatorRepository repository(
      http.Response Function(http.Request request) respond) {
    requests = [];
    final account = LiveAccountRepository(
        ApiClient('https://api.example.test/api/v1',
            client: MockClient((request) async {
          if (request.url.path.endsWith('/auth/refresh')) {
            return http.Response(
                jsonEncode({'access_token': 'access', 'refresh_token': 'r2'}),
                200);
          }
          expect(request.headers['Authorization'], 'Bearer access');
          requests.add(request);
          return respond(request);
        })),
        UnusedCredentials2());
    return LiveOwnCreatorRepository(account);
  }

  test('reads the signed-in creator from GET /creators/me', () async {
    final repo =
        repository((_) => http.Response(jsonEncode(profileJson()), 200));
    final own = await repo.profile();
    expect(requests.single.method, 'GET');
    expect(requests.single.url.path, '/api/v1/creators/me');
    expect(own.handle, 'amakollie');
    expect(own.title, 'Ama Kollie');
    expect(ownTitleFallback(), '@amakollie');
  });

  test('rejects profiles that break the DOC-205 shape', () async {
    for (final broken in [
      profileJson(extra: {'follower_count': 3}),
      profileJson(status: 'suspended'),
      profileJson(handle: 'has space'),
      profileJson(name: 'x' * 81),
      profileJson(bio: 'x' * 501),
      {...profileJson()}..remove('location'),
    ]) {
      final repo = repository((_) => http.Response(jsonEncode(broken), 200));
      await expectLater(repo.profile(), throwsFormatException,
          reason: '$broken');
    }
  });

  test('preserves legacy handles the new rule would reject', () async {
    final repo = repository(
        (_) => http.Response(jsonEncode(profileJson(handle: 'Ama-K')), 200));
    expect((await repo.profile()).handle, 'Ama-K');
  });

  test('PATCH sends only the changed, trimmed fields', () async {
    final repo = repository((request) {
      final body = jsonDecode(request.body) as Map<String, dynamic>;
      return http.Response(
          jsonEncode(profileJson(name: body['display_name'] as String)), 200);
    });
    final current = OwnCreator.fromJson(profileJson());
    final updated = await repo.update(current,
        displayName: '  Ama K.  ',
        bio: current.bio,
        location: current.location,
        handle: current.handle);
    expect(requests.single.method, 'PATCH');
    expect(requests.single.url.path, '/api/v1/creators/me');
    expect(jsonDecode(requests.single.body), {'display_name': 'Ama K.'});
    expect(updated.displayName, 'Ama K.');
  });

  test('input the server would reject never leaves the device', () async {
    final repo =
        repository((_) => http.Response(jsonEncode(profileJson()), 200));
    final current = OwnCreator.fromJson(profileJson());
    final invalid = <Future<OwnCreator> Function()>[
      () => repo.update(current, handle: 'Ama'), // uppercase
      () => repo.update(current, handle: 'ama kollie'), // space
      () => repo.update(current, handle: 'am'), // too short
      () => repo.update(current, handle: 'a' * 31), // too long
      () => repo.update(current, displayName: 'x' * 81),
      () => repo.update(current, bio: 'x' * 501),
      () => repo.update(current, location: 'x' * 81),
      () => repo.update(current, displayName: 'bad\u0000name'),
      () => repo.update(current, location: 'line\nbreak'), // bio only
      () => repo.update(current), // nothing to save
      () => repo.update(current, displayName: current.displayName),
    ];
    for (final call in invalid) {
      await expectLater(call(), throwsFormatException);
    }
    expect(requests, isEmpty);
    // Bio may contain line breaks (the gateway allows \n, \r, \t there).
    await repo.update(current, bio: 'one\ntwo').catchError((_) => current);
    expect(jsonDecode(requests.single.body), {'bio': 'one\ntwo'});
  });

  test('handle_taken keeps its stable code and status', () async {
    final repo = repository((_) => http.Response(
        jsonEncode({
          'detail': 'Creator handle is unavailable',
          'code': 'handle_taken'
        }),
        409));
    await expectLater(
        repo.update(OwnCreator.fromJson(profileJson()), handle: 'taken_one'),
        throwsA(isA<ApiFailure>()
            .having((e) => e.status, 'status', 409)
            .having((e) => e.code, 'code', 'handle_taken')));
  });

  test('a response that does not echo the change is rejected', () async {
    final repo = repository((_) =>
        http.Response(jsonEncode(profileJson(name: 'Someone Else')), 200));
    await expectLater(
        repo.update(OwnCreator.fromJson(profileJson()), displayName: 'Ama K.'),
        throwsFormatException);
  });

  test('creator access: role and restriction failures map to their kinds',
      () async {
    for (final entry
        in {403: FailureKind.forbidden, 404: FailureKind.notFound}.entries) {
      final repo = repository(
          (_) => http.Response(jsonEncode({'detail': 'No'}), entry.key));
      await expectLater(
          repo.profile(),
          throwsA(
              isA<ApiFailure>().having((e) => e.kind, 'kind', entry.value)));
    }
  });

  group('onboarding handle rule (DOC-205 ^[a-z0-9_]{3,30}\$)', () {
    test('accepts valid handles and reports a reason for invalid ones', () {
      for (final ok in ['ama', 'ama_kollie', 'a1_', '_' * 30]) {
        expect(creatorHandleProblem(ok), isNull, reason: ok);
      }
      for (final bad in [
        '',
        'ab',
        'a' * 31,
        'Ama',
        'ama kollie',
        'ama-kollie',
        'ama.k',
        'ámá'
      ]) {
        expect(creatorHandleProblem(bad), isNotNull, reason: bad);
      }
    });

    test('application submission refuses what the server would reject',
        () async {
      var sent = 0;
      final account = LiveAccountRepository(
          ApiClient('https://api.example.test/api/v1',
              client: MockClient((request) async {
            if (request.url.path.endsWith('/auth/refresh')) {
              return http.Response(
                  jsonEncode({'access_token': 'a', 'refresh_token': 'b'}), 200);
            }
            sent++;
            return http.Response(
                jsonEncode({
                  'account_id': accountId,
                  'status': 'pending',
                  'creator_id': null
                }),
                201);
          })),
          UnusedCredentials2());
      final onboarding = LiveCreatorOnboardingRepository(account);
      for (final handle in [
        'Storyteller',
        'story-teller',
        'ab',
        'story teller'
      ]) {
        await expectLater(
            onboarding.submit(
                handle: handle, adultAttested: true, rightsAttested: true),
            throwsFormatException,
            reason: handle);
      }
      expect(sent, 0);
      expect(
          (await onboarding.submit(
                  handle: ' storyteller ',
                  adultAttested: true,
                  rightsAttested: true))
              .status,
          'pending');
      expect(sent, 1);
    });
  });
}

String ownTitleFallback() =>
    const OwnCreator('i', 'u', 'amakollie', '', '', '').title;

/// A credential store holding a refresh token so the account can sign in.
class UnusedCredentials2 extends UnusedCredentials {
  @override
  Future<String?> readRefreshToken() async => 'refresh';
}
