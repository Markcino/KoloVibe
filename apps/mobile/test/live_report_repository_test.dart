import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/features/account/live_account_repository.dart';
import 'package:kolovibe/features/moderation/live_moderation_repository.dart';

import 'live_own_creator_repository_test.dart' show UnusedCredentials2;
import 'support/upload_fakes.dart';

/// Repository contract tests with mocked HTTP (`MockClient`) for the report
/// calls in `services/gateway/service/moderation.py`.
void main() {
  late List<http.Request> requests;

  LiveModerationRepository repository(
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
    return LiveModerationRepository(account);
  }

  String id(int n) =>
      '00000000-0000-4000-8000-${(0x100000 + n).toRadixString(16).padLeft(12, '0')}';

  Map<String, Object?> recordJson(int n,
          {String video = videoId,
          String status = 'open',
          String reason = 'copyright',
          Map<String, Object?> change = const {}}) =>
      {
        'id': id(n),
        'video_id': video,
        'status': status,
        'created_at': '2026-11-11T12:00:00Z',
        'reason': reason,
        'details': 'private text',
        ...change,
      };

  http.Response page(List<Map<String, Object?>> items, [String? next]) =>
      http.Response(jsonEncode({'items': items, 'next_cursor': next}), 200);

  group('own reports', () {
    test('reads GET /me/reports with the reason of each report', () async {
      final repo = repository((_) => page([recordJson(1, reason: 'spam')]));
      final result = await repo.ownReports();
      expect(requests.single.method, 'GET');
      expect(requests.single.url.path, '/api/v1/me/reports');
      expect(result.items.single.reason, 'spam');
      expect(result.items.single.isOpen, isTrue);
      expect(result.nextCursor, isNull);
    });

    test('rejects records the gateway would never send', () async {
      for (final broken in [
        recordJson(1, reason: 'violence'),
        recordJson(1, status: 'approved'),
        recordJson(1, change: {'details': null}),
        recordJson(1, change: {'video_id': 'x'}),
        recordJson(1, change: {'reviewer': 'someone'}),
        recordJson(1)..remove('reason'),
      ]) {
        final repo = repository((_) => page([broken]));
        await expectLater(repo.ownReports(), throwsFormatException,
            reason: '$broken');
      }
    });

    test('enforces the paging contract', () async {
      await expectLater(
          repository((_) => page([recordJson(1)], id(1))).ownReports(),
          completion(isA<ReportPage>()));
      await expectLater(
          repository((_) => page([recordJson(1)], id(2))).ownReports(),
          throwsFormatException);
      await expectLater(repository((_) => page([], id(2))).ownReports(),
          throwsFormatException);
      await expectLater(
          repository((_) => page([recordJson(1)], id(1)))
              .ownReports(cursor: id(1)),
          throwsFormatException);
      await expectLater(
          repository((_) => page([recordJson(1), recordJson(1)])).ownReports(),
          throwsFormatException);
      await expectLater(
          repository((_) => page([for (var n = 1; n <= 21; n++) recordJson(n)]))
              .ownReports(),
          throwsFormatException);
      await expectLater(
          repository((_) => http.Response(jsonEncode({'items': []}), 200))
              .ownReports(),
          throwsFormatException);
    });

    test('a bad cursor is refused before any request', () async {
      final repo = repository((_) => page([]));
      await expectLater(repo.ownReports(cursor: '../x'), throwsFormatException);
      expect(requests, isEmpty);
    });
  });

  group('findReport', () {
    test('walks pages until it finds the video, sending each cursor', () async {
      final repo = repository((request) {
        final cursor = request.url.queryParameters['cursor'];
        return switch (cursor) {
          null => page([recordJson(1, video: id(80))], id(1)),
          _ when cursor == id(1) => page([recordJson(2, video: id(81))], id(2)),
          _ => page([recordJson(3)]),
        };
      });
      final found = await repo.findReport(videoId);
      expect(found!.id, id(3));
      expect(requests.map((r) => r.url.queryParameters['cursor']),
          [null, id(1), id(2)]);
    });

    test('openOnly skips a decided report for the same video', () async {
      final repo = repository((_) => page([
            recordJson(1, status: 'resolved'),
            recordJson(2, status: 'open'),
          ]));
      expect((await repo.findReport(videoId, openOnly: true))!.id, id(2));
      expect((await repo.findReport(videoId))!.id, id(1));
    });

    test('is bounded and reports null rather than guessing', () async {
      var calls = 0;
      final repo = repository((_) {
        calls++;
        return page([recordJson(calls, video: id(80))], id(calls));
      });
      expect(await repo.findReport(videoId, maxPages: 3), isNull);
      expect(requests, hasLength(3));
    });

    test('an invalid video id never reaches the network', () async {
      final repo = repository((_) => page([]));
      await expectLater(repo.findReport('nope'), throwsFormatException);
      expect(requests, isEmpty);
    });
  });

  group('submitting a report', () {
    const key = 'abcdefghijklmnop1234';

    http.Response created() => http.Response(
        jsonEncode({
          'id': id(1),
          'video_id': videoId,
          'status': 'open',
          'created_at': '2026-11-11T12:00:00Z'
        }),
        201);

    test('sends the key header and only the three fields', () async {
      final repo = repository((_) => created());
      await repo.report(
          videoId: videoId, reason: 'copyright', details: 'x', key: key);
      final request = requests.single;
      expect(request.method, 'POST');
      expect(request.headers['Idempotency-Key'], key);
      expect(jsonDecode(request.body),
          {'video_id': videoId, 'reason': 'copyright', 'details': 'x'});
    });

    test('an identical retry sends the same key and body', () async {
      final repo = repository((_) => created());
      for (var i = 0; i < 2; i++) {
        await repo.report(
            videoId: videoId, reason: 'spam', details: 'same', key: key);
      }
      expect(requests.map((r) => r.headers['Idempotency-Key']).toSet(), {key});
      expect(requests.map((r) => r.body).toSet(), hasLength(1));
    });

    test('a 409 already_reported keeps its code', () async {
      final repo = repository((_) => http.Response(
          jsonEncode({
            'detail': 'You already have an open report for this video.',
            'code': 'already_reported'
          }),
          409));
      await expectLater(
          repo.report(videoId: videoId, reason: 'spam', details: '', key: key),
          throwsA(predicate(LiveModerationRepository.isAlreadyReported)));
    });

    test('any other 409 is a plain conflict', () async {
      final repo = repository((_) =>
          http.Response(jsonEncode({'detail': 'Idempotency conflict'}), 409));
      await expectLater(
          repo.report(videoId: videoId, reason: 'spam', details: '', key: key),
          throwsA(isA<ApiFailure>()
              .having((f) => LiveModerationRepository.isAlreadyReported(f),
                  'already reported', false)
              .having((f) => f.kind, 'kind', FailureKind.conflict)));
    });

    test('details over 2000 characters are refused before any request',
        () async {
      final repo = repository((_) => created());
      await expectLater(
          repo.report(
              videoId: videoId, reason: 'spam', details: 'x' * 2001, key: key),
          throwsFormatException);
      expect(requests, isEmpty);
    });
  });
}
