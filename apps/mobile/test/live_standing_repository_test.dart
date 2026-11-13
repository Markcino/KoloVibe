import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/features/account/live_account_repository.dart';
import 'package:kolovibe/features/moderation/live_standing_repository.dart';

import 'live_own_creator_repository_test.dart' show UnusedCredentials2;
import 'support/upload_fakes.dart';

/// Repository contract tests with mocked HTTP (`MockClient`) for the notice
/// and standing shapes in `services/gateway/service/standing.py`.
void main() {
  late List<http.Request> requests;

  LiveStandingRepository repository(
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
          requests.add(request);
          return respond(request);
        })),
        UnusedCredentials2());
    return LiveStandingRepository(account);
  }

  const appealId = '00000000-0000-4000-8000-000000000a01';

  Map<String, Object?> appealJson({Map<String, Object?> change = const {}}) => {
        'id': appealId,
        'video_id': videoId,
        'status': 'open',
        'created_at': '2026-11-02T09:00:00Z',
        'reason': 'The audio is licensed to me.',
        ...change,
      };

  Map<String, Object?> noticeJson({Map<String, Object?> change = const {}}) => {
        'video_id': videoId,
        'decision': 'removed',
        'reason_code': 'REVIEWED_REMOVE',
        'decided_at': '2026-10-28T12:00:00Z',
        'appealable': false,
        'appeal': null,
        ...change,
      };

  http.Response json(Object body) => http.Response(jsonEncode(body), 200);

  group('notice', () {
    test('reads GET /creators/me/videos/{id}/notice', () async {
      final repo =
          repository((_) => json(noticeJson(change: {'appealable': true})));
      final notice = await repo.notice(videoId);
      expect(requests.single.method, 'GET');
      expect(requests.single.url.path,
          '/api/v1/creators/me/videos/$videoId/notice');
      expect(notice.decision, 'removed');
      expect(notice.reasonCode, 'REVIEWED_REMOVE');
      expect(notice.appealable, isTrue);
      expect(notice.appeal, isNull);
    });

    test('parses every decision, a null reason and the own appeal', () async {
      for (final decision in [
        'rejected',
        'removed',
        'restricted',
        'restored'
      ]) {
        final repo =
            repository((_) => json(noticeJson(change: {'decision': decision})));
        expect((await repo.notice(videoId)).decision, decision);
      }
      final none = await repository((_) => json(noticeJson(change: {
            'decision': 'none',
            'reason_code': null,
            'decided_at': null,
          }))).notice(videoId);
      expect(none.hasDecision, isFalse);
      final appealed = await repository(
              (_) => json(noticeJson(change: {'appeal': appealJson()})))
          .notice(videoId);
      expect(appealed.appeal!.status, 'open');
      expect(appealed.appeal!.reason, 'The audio is licensed to me.');
    });

    test('rejects notices the gateway would never send', () async {
      for (final broken in [
        noticeJson(change: {'decision': 'banned'}),
        noticeJson(change: {'reason_code': 'lowercase'}),
        noticeJson(change: {'reason_code': 'A'}),
        noticeJson(change: {'decided_at': '2026-10-28 12:00'}),
        noticeJson(change: {'decided_at': null}),
        noticeJson(change: {'appealable': 'yes'}),
        // Only a removal with no appeal yet is appealable.
        noticeJson(change: {'decision': 'rejected', 'appealable': true}),
        noticeJson(change: {'appealable': true, 'appeal': appealJson()}),
        noticeJson(change: {
          'appeal': appealJson(change: {'status': 'granted'})
        }),
        noticeJson(change: {
          'appeal': appealJson(change: {'video_id': appealId})
        }),
        noticeJson(change: {
          'appeal': appealJson(change: {'reason': 'short'})
        }),
        noticeJson(change: {
          'appeal': appealJson(change: {'created_at': 'soon'})
        }),
        noticeJson(change: {'reviewer': 'someone'}),
        noticeJson()..remove('appeal'),
      ]) {
        final repo = repository((_) => json(broken));
        await expectLater(repo.notice(videoId), throwsFormatException,
            reason: '$broken');
      }
    });

    test('rejects a notice for a different video', () async {
      final repo = repository((_) => json(noticeJson(
          change: {'video_id': '00000000-0000-4000-8000-0000000000ff'})));
      await expectLater(repo.notice(videoId), throwsFormatException);
    });

    test('an invalid id never reaches the network', () async {
      final repo = repository((_) => json(noticeJson()));
      await expectLater(repo.notice('../me'), throwsFormatException);
      expect(requests, isEmpty);
    });

    test('a foreign video and a non-creator are normal failure states',
        () async {
      final missing = repository(
          (_) => http.Response(jsonEncode({'detail': 'Video not found'}), 404));
      await expectLater(
          missing.notice(videoId),
          throwsA(isA<ApiFailure>()
              .having((f) => f.kind, 'kind', FailureKind.notFound)));
      final viewer = repository((_) =>
          http.Response(jsonEncode({'detail': 'Creator role required'}), 403));
      await expectLater(
          viewer.notice(videoId),
          throwsA(isA<ApiFailure>()
              .having((f) => f.kind, 'kind', FailureKind.forbidden)));
    });
  });

  group('standing', () {
    Map<String, Object?> standingJson(
            {Map<String, Object?> change = const {}}) =>
        {
          'account_status': 'active',
          'creator_status': 'active',
          'publishing_allowed': true,
          'notices': <Object?>[],
          ...change,
        };

    test('reads GET /me/standing', () async {
      final repo = repository((_) => json(standingJson(change: {
            'notices': [noticeJson()]
          })));
      final standing = await repo.standing();
      expect(requests.single.method, 'GET');
      expect(requests.single.url.path, '/api/v1/me/standing');
      expect(standing.creatorStatus, 'active');
      expect(standing.publishingAllowed, isTrue);
      expect(standing.notices.single.decision, 'removed');
    });

    test('a viewer has no creator status and cannot publish', () async {
      final repo = repository((_) => json(standingJson(
          change: {'creator_status': null, 'publishing_allowed': false})));
      final standing = await repo.standing();
      expect(standing.creatorStatus, isNull);
      expect(standing.publishingAllowed, isFalse);
    });

    test('rejects standings the gateway would never send', () async {
      for (final broken in [
        standingJson(change: {'account_status': 'suspended'}),
        standingJson(change: {'creator_status': 'banned'}),
        standingJson(change: {'publishing_allowed': 'true'}),
        // Publishing needs an active creator.
        standingJson(change: {
          'creator_status': 'restricted',
          'publishing_allowed': true
        }),
        standingJson(
            change: {'creator_status': null, 'publishing_allowed': true}),
        standingJson(change: {'notices': 'none'}),
        standingJson(change: {
          'notices': [
            for (var n = 0; n < 21; n++)
              noticeJson(change: {
                'video_id':
                    '00000000-0000-4000-8000-${(0x300000 + n).toRadixString(16).padLeft(12, '0')}'
              })
          ]
        }),
        standingJson(change: {
          'notices': [noticeJson(), noticeJson()]
        }),
        standingJson(change: {
          'notices': [
            noticeJson(change: {'decision': 'x'})
          ]
        }),
        standingJson(change: {'extra': 1}),
        standingJson()..remove('notices'),
      ]) {
        final repo = repository((_) => json(broken));
        await expectLater(repo.standing(), throwsFormatException,
            reason: '$broken');
      }
    });

    test('a 503 from a dependency is an unavailable state', () async {
      final repo = repository((_) => http.Response(
          jsonEncode({'detail': 'Moderation temporarily unavailable'}), 503));
      await expectLater(repo.standing(),
          throwsA(isA<ApiFailure>().having((f) => f.status, 'status', 503)));
    });
  });

  test('every call is a GET with no body', () async {
    final repo = repository((request) => request.url.path.endsWith('/standing')
        ? json({
            'account_status': 'active',
            'creator_status': null,
            'publishing_allowed': false,
            'notices': <Object?>[]
          })
        : json(noticeJson()));
    await repo.standing();
    await repo.notice(videoId);
    expect(requests.map((r) => r.method).toSet(), {'GET'});
    expect(requests.every((r) => r.bodyBytes.isEmpty), isTrue);
  });
}
