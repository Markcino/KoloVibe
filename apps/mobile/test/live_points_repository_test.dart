import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/features/account/live_account_repository.dart';
import 'package:kolovibe/features/points/live_points_repository.dart';

import 'live_own_creator_repository_test.dart' show UnusedCredentials2;
import 'support/upload_fakes.dart';

/// Repository contract tests with mocked HTTP (`MockClient`): the gateway
/// shapes from `services/gateway/service/pilot_points.py` are asserted, but no
/// gateway, network or device is involved.
void main() {
  late List<http.Request> requests;

  LivePointsRepository repository(
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
    return LivePointsRepository(account);
  }

  String id(int n) =>
      '00000000-0000-4000-8000-${(0x100000 + n).toRadixString(16).padLeft(12, '0')}';

  Map<String, Object?> balanceJson({Map<String, Object?> change = const {}}) =>
      {
        'creator_id': creatorId,
        'balance': 1240,
        'currency': 'POINTS',
        'as_of': '2026-11-11T12:00:00Z',
        'confirmed': 1260,
        'pending': 160,
        'withheld': 40,
        'reversed': 20,
        ...change,
      };

  Map<String, Object?> entryJson(int n,
          {String kind = 'award',
          String status = 'confirmed',
          int amount = 1,
          String? video,
          Map<String, Object?> change = const {}}) =>
      {
        'id': id(n),
        'creator_id': creatorId,
        'amount': amount,
        'kind': kind,
        'rule_version': 'DEC-003-v1',
        'created_at': '2026-11-11T12:00:00Z',
        'status': status,
        'video_id': video,
        ...change,
      };

  http.Response page(List<Map<String, Object?>> items, [String? next]) =>
      http.Response(jsonEncode({'items': items, 'next_cursor': next}), 200);

  group('balance', () {
    test('reads GET /creators/me/points and keeps the server totals', () async {
      final repo =
          repository((_) => http.Response(jsonEncode(balanceJson()), 200));
      final balance = await repo.balance();
      expect(requests.single.method, 'GET');
      expect(requests.single.url.path, '/api/v1/creators/me/points');
      expect(balance.balance, 1240);
      // Category totals are the server's, not derived from `balance`.
      expect([
        balance.confirmed,
        balance.pending,
        balance.withheld,
        balance.reversed
      ], [
        1260,
        160,
        40,
        20
      ]);
    });

    test('rejects a balance that breaks the gateway shape', () async {
      for (final broken in [
        balanceJson(change: {'pending': null}),
        balanceJson(change: {'withheld': -1}),
        balanceJson(change: {'reversed': '20'}),
        balanceJson(change: {'currency': 'USD'}),
        balanceJson(change: {'creator_id': 'not-a-uuid'}),
        balanceJson(change: {'as_of': 'yesterday'}),
        balanceJson(change: {'cash_value': 12}),
        (balanceJson()..remove('confirmed')),
      ]) {
        final repo = repository((_) => http.Response(jsonEncode(broken), 200));
        await expectLater(repo.balance(), throwsFormatException,
            reason: '$broken');
      }
    });

    test('maps gateway failures instead of inventing a balance', () async {
      final forbidden = repository((_) => http.Response(
          jsonEncode({'detail': 'Approved creator required'}), 403));
      await expectLater(
          forbidden.balance(),
          throwsA(isA<ApiFailure>()
              .having((f) => f.kind, 'kind', FailureKind.forbidden)));
      final down = repository((_) => http.Response(
          jsonEncode({'detail': 'Points service unavailable'}), 503));
      await expectLater(down.balance(),
          throwsA(isA<ApiFailure>().having((f) => f.status, 'status', 503)));
    });
  });

  group('entries', () {
    test('sends the cursor and the server status filter', () async {
      final repo = repository(
          (request) => switch (request.url.queryParameters['status']) {
                'confirmed' => page([entryJson(1)]),
                'adjustments' => page([
                    entryJson(2,
                        kind: 'reversal', status: 'adjustments', amount: -20)
                  ]),
                _ => page([entryJson(1)]),
              });
      await repo.entries();
      expect(requests.last.url.queryParameters, isEmpty);
      await repo.entries(filter: PointsFilter.confirmed);
      expect(requests.last.url.queryParameters, {'status': 'confirmed'});
      await repo.entries(filter: PointsFilter.adjustments, cursor: id(9));
      expect(requests.last.url.queryParameters,
          {'status': 'adjustments', 'cursor': id(9)});
      expect(requests.map((r) => r.method).toSet(), {'GET'});
      expect(requests.last.url.path, '/api/v1/creators/me/points/entries');
    });

    test('parses status and source video for every entry state', () async {
      final repo = repository((_) => page([
            entryJson(1, video: id(50)),
            entryJson(2, status: 'pending', amount: 1),
            entryJson(3, status: 'withheld'),
            entryJson(4, kind: 'reversal', status: 'adjustments', amount: -20),
            entryJson(5, kind: 'adjustment', status: 'adjustments', amount: 5),
          ]));
      final items = (await repo.entries()).items;
      expect(items.map((e) => e.status),
          ['confirmed', 'pending', 'withheld', 'adjustments', 'adjustments']);
      expect(items.first.videoId, id(50));
      expect(items[1].videoId, isNull);
      expect(items[3].isReversal, isTrue);
      expect(items[2].isWithheld, isTrue);
    });

    test('rejects entries the gateway would never send', () async {
      for (final broken in [
        entryJson(1, amount: 0),
        entryJson(1, amount: -1), // a negative award
        entryJson(1, kind: 'reversal', status: 'adjustments', amount: 20),
        entryJson(1, kind: 'reversal'), // reversal must be an adjustment
        entryJson(1, status: 'adjustments'), // award cannot be an adjustment
        entryJson(1, status: 'posted'),
        entryJson(1, change: {'status': null}),
        entryJson(1, change: {'video_id': 'nope'}),
        entryJson(1, change: {'rule_version': ''}),
        entryJson(1, change: {'created_at': 'soon'}),
        entryJson(1, change: {'payout': 1}),
        entryJson(1)..remove('status'),
      ]) {
        final repo = repository((_) => page([broken]));
        await expectLater(repo.entries(), throwsFormatException,
            reason: '$broken');
      }
    });

    test('rejects a page that does not match the requested filter', () async {
      final repo = repository((_) => page([entryJson(1, status: 'pending')]));
      await expectLater(
          repo.entries(filter: PointsFilter.confirmed), throwsFormatException);
    });

    test('enforces the paging contract', () async {
      final full = [for (var n = 1; n <= 20; n++) entryJson(n)];
      // A cursor is valid only on a full page and must be its last id.
      await expectLater(repository((_) => page(full, id(20))).entries(),
          completion(isA<PointsPage>()));
      await expectLater(repository((_) => page(full, id(19))).entries(),
          throwsFormatException);
      await expectLater(
          repository((_) => page([entryJson(1)], id(1))).entries(),
          throwsFormatException);
      await expectLater(
          repository((_) => page(full, id(20))).entries(cursor: id(20)),
          throwsFormatException);
      await expectLater(
          repository((_) => page([...full, entryJson(21)])).entries(),
          throwsFormatException);
      await expectLater(
          repository((_) => page([entryJson(1), entryJson(1)])).entries(),
          throwsFormatException);
      await expectLater(
          repository((_) => http.Response(jsonEncode({'items': []}), 200))
              .entries(),
          throwsFormatException);
    });

    test('a bad cursor is refused before any request', () async {
      final repo = repository((_) => page([]));
      await expectLater(repo.entries(cursor: '../x'), throwsFormatException);
      expect(requests, isEmpty);
    });
  });

  group('entry', () {
    test('reads the owner-only entry by id', () async {
      final repo = repository(
          (_) => http.Response(jsonEncode(entryJson(7, video: id(60))), 200));
      final entry = await repo.entry(id(7));
      expect(requests.single.method, 'GET');
      expect(requests.single.url.path,
          '/api/v1/creators/me/points/entries/${id(7)}');
      expect(entry.videoId, id(60));
    });

    test('rejects a different entry than the one requested', () async {
      final repo =
          repository((_) => http.Response(jsonEncode(entryJson(8)), 200));
      await expectLater(repo.entry(id(7)), throwsFormatException);
    });

    test('a foreign or missing id is a normal not-found state', () async {
      final repo = repository(
          (_) => http.Response(jsonEncode({'detail': 'Not found'}), 404));
      await expectLater(
          repo.entry(id(7)),
          throwsA(isA<ApiFailure>()
              .having((f) => f.kind, 'kind', FailureKind.notFound)));
    });

    test('an invalid id never reaches the network', () async {
      final repo = repository((_) => http.Response('{}', 200));
      await expectLater(repo.entry('1/../../me'), throwsFormatException);
      expect(requests, isEmpty);
    });
  });

  group('the client cannot change points', () {
    test('the gateway only offers GET, and every call here is a GET', () async {
      final repo = repository((request) => switch (request.url.path) {
            final p when p.endsWith('/points') =>
              http.Response(jsonEncode(balanceJson()), 200),
            final p when p.endsWith('/entries') => page([entryJson(1)]),
            _ => http.Response(jsonEncode(entryJson(1)), 200),
          });
      await repo.balance();
      await repo.entries();
      await repo.entry(id(1));
      expect(requests.map((r) => r.method).toSet(), {'GET'});
      expect(requests.every((r) => r.bodyBytes.isEmpty), isTrue);
    });

    test('points code has no write verb, award or computation hooks', () {
      final sources = Directory('lib/features/points')
          .listSync()
          .whereType<File>()
          .where((file) => file.path.endsWith('.dart'));
      expect(sources, isNotEmpty);
      for (final file in sources) {
        final code = file.readAsStringSync();
        expect(code, isNot(contains('method:')), reason: file.path);
        expect(code, isNot(matches(RegExp(r"'(POST|PUT|PATCH|DELETE)'"))),
            reason: file.path);
        expect(code, isNot(contains('idempotencyKey')), reason: file.path);
        // No summing or arithmetic over amounts or balances.
        expect(code, isNot(matches(RegExp(r'\.(fold|reduce)\('))),
            reason: file.path);
        expect(
            code, isNot(matches(RegExp(r'(amount|balance)\s*[+*/-]=?\s*\w'))),
            reason: file.path);
      }
    });
  });
}
