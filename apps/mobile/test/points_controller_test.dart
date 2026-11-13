import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/features/points/live_points_repository.dart';
import 'package:kolovibe/features/points/points_controller.dart';

import 'support/points_fakes.dart';
import 'support/upload_fakes.dart';

/// Controller tests with a scripted (fake) points service. No HTTP.
void main() {
  late ScriptedPoints service;
  setUp(() => service = ScriptedPoints(pageSize: 3));

  List<PointsEntry> ledger(int count, {String status = 'confirmed'}) =>
      [for (var n = 1; n <= count; n++) ledgerEntry(n, status: status)];

  group('ledger paging', () {
    test('loads the balance and the first page, and keeps the cursor',
        () async {
      service.ledger = ledger(7);
      final controller = PointsController(service, PointsView.history);
      await controller.load();
      expect(controller.phase, PointsPhase.ready);
      expect(controller.entries.map((e) => e.id), [1, 2, 3].map(entryId));
      expect(controller.hasMore, isTrue);
    });

    test('shows the server balance even when the rows do not add up to it',
        () async {
      // The server owns the figure; the client never sums rows into it.
      service
        ..current = serverBalance(balance: 1240)
        ..ledger = ledger(3);
      final controller = PointsController(service, PointsView.overview);
      await controller.load();
      expect(controller.balance!.balance, 1240);
      expect(controller.entries.fold<int>(0, (sum, e) => sum + e.amount), 3);
    });

    test('loadMore appends pages until the server has no cursor', () async {
      service.ledger = ledger(7);
      final controller = PointsController(service, PointsView.history);
      await controller.load();
      await controller.loadMore();
      await controller.loadMore();
      expect(controller.entries, hasLength(7));
      expect(controller.hasMore, isFalse);
      await controller.loadMore(); // nothing more: no request
      expect(service.entryReads, hasLength(3));
      expect(service.entryReads[1].cursor, entryId(3));
      expect(service.entryReads[2].cursor, entryId(6));
    });

    test('only one page is in flight at a time', () async {
      service.ledger = ledger(9);
      final controller = PointsController(service, PointsView.history);
      await controller.load();
      final gate = service.gate = Completer<void>();
      final first = controller.loadMore();
      final second = controller.loadMore();
      expect(controller.loadingMore, isTrue);
      gate.complete();
      await Future.wait([first, second]);
      expect(controller.entries, hasLength(6));
      expect(service.entryReads, hasLength(2));
    });

    test('a failed page keeps the rows and retries from the same cursor',
        () async {
      service.ledger = ledger(7);
      final controller = PointsController(service, PointsView.history);
      await controller.load();
      service.entryFailures.add(offlineFailure);
      await controller.loadMore();
      expect(controller.moreError, isA<ApiFailure>());
      expect(controller.entries, hasLength(3));
      expect(controller.phase, PointsPhase.ready);
      await controller.loadMore();
      expect(controller.moreError, isNull);
      expect(controller.entries, hasLength(6));
      expect(service.entryReads.last.cursor, entryId(3));
    });

    test('a repeated row is refused rather than shown twice', () async {
      final replaying = _Replaying(service..ledger = ledger(7));
      final controller = PointsController(replaying, PointsView.history);
      await controller.load();
      await controller.loadMore(); // the server replays page one
      expect(controller.moreError, isA<ApiFailure>());
      expect(controller.entries, hasLength(3));
    });

    test('rows that belong to another creator are never shown', () async {
      service.ledger = [
        ledgerEntry(1),
        ledgerEntry(2, creator: '00000000-0000-4000-8000-0000000000ff'),
      ];
      final controller = PointsController(service, PointsView.history);
      await controller.load();
      expect(controller.phase, PointsPhase.failed);
      expect(controller.entries, isEmpty);
    });
  });

  group('filters', () {
    test('each view asks the server for its own status', () async {
      service.ledger = [
        ledgerEntry(1),
        ledgerEntry(2, status: 'pending'),
        ledgerEntry(3, status: 'adjustments'),
      ];
      for (final (view, filter) in [
        (PointsView.confirmed, PointsFilter.confirmed),
        (PointsView.pending, PointsFilter.pending),
        (PointsView.adjustments, PointsFilter.adjustments),
        (PointsView.overview, PointsFilter.all),
      ]) {
        service.entryReads.clear();
        final controller = PointsController(service, view);
        await controller.load();
        expect(service.entryReads.single.filter, filter, reason: '$view');
      }
    });

    test('history switches filter and reloads from the first page', () async {
      service.ledger = [
        ledgerEntry(1),
        ledgerEntry(2, status: 'pending'),
        ledgerEntry(3),
        ledgerEntry(4),
        ledgerEntry(5),
      ];
      final controller = PointsController(service, PointsView.history);
      await controller.load();
      await controller.loadMore();
      await controller.setFilter(PointsFilter.pending);
      expect(controller.filter, PointsFilter.pending);
      expect(controller.entries.map((e) => e.status), ['pending']);
      expect(service.entryReads.last.cursor, isNull);
      expect(service.entryReads.last.filter, PointsFilter.pending);
    });

    test('a slow response for an old filter cannot overwrite the new one',
        () async {
      service.ledger = [
        ledgerEntry(1),
        ledgerEntry(2, status: 'pending'),
      ];
      final controller = PointsController(service, PointsView.history);
      final gate = service.gate = Completer<void>();
      final slow = controller.load(); // all filter, held at the gate
      await Future<void>.delayed(Duration.zero);
      service.gate = null;
      await controller.setFilter(PointsFilter.pending);
      gate.complete();
      await slow;
      expect(controller.filter, PointsFilter.pending);
      expect(controller.entries.map((e) => e.status), ['pending']);
    });
  });

  group('withheld view', () {
    test('picks withheld rows out of the all pages, in server order', () async {
      service.ledger = [
        ledgerEntry(1),
        ledgerEntry(2, status: 'withheld'),
        ledgerEntry(3),
        ledgerEntry(4, status: 'withheld'),
      ];
      final controller = PointsController(service, PointsView.withheld);
      await controller.load();
      expect(service.entryReads.every((r) => r.filter == PointsFilter.all),
          isTrue);
      expect(controller.entries.map((e) => e.id), [2].map(entryId));
      await controller.loadMore();
      expect(controller.entries.map((e) => e.id), [2, 4].map(entryId));
    });

    test('keeps reading when a page has none, then stops at the bound',
        () async {
      service = ScriptedPoints(pageSize: 1)
        ..ledger = [
          for (var n = 1; n <= 9; n++) ledgerEntry(n),
        ];
      final controller = PointsController(service, PointsView.withheld);
      await controller.load();
      // One first page plus at most maxAutoPages more: bounded, not endless.
      expect(service.entryReads, hasLength(1 + PointsController.maxAutoPages));
      expect(controller.entries, isEmpty);
      expect(controller.hasMore, isTrue);
      expect(controller.loadingMore, isFalse);
    });

    test('an empty ledger ends without a cursor', () async {
      final controller = PointsController(service, PointsView.withheld);
      await controller.load();
      expect(controller.entries, isEmpty);
      expect(controller.hasMore, isFalse);
    });
  });

  group('errors and refresh', () {
    test('a points failure is the failed state with a retry', () async {
      service.balanceFailure = offlineFailure;
      final controller = PointsController(service, PointsView.overview);
      await controller.load();
      expect(controller.phase, PointsPhase.failed);
      expect((controller.error as ApiFailure).kind, FailureKind.offline);
      service.balanceFailure = null;
      service.ledger = ledger(1);
      await controller.load();
      expect(controller.phase, PointsPhase.ready);
    });

    test('an unapproved creator is a forbidden state, not a crash', () async {
      service.balanceFailure = notCreator;
      final controller = PointsController(service, PointsView.overview);
      await controller.load();
      expect((controller.error as ApiFailure).kind, FailureKind.forbidden);
    });

    test('an unreadable response never shows partial data', () async {
      service.ledger = ledger(2);
      final controller =
          PointsController(_Unreadable(service), PointsView.overview);
      await controller.load();
      expect(controller.phase, PointsPhase.failed);
      expect(controller.balance, isNull);
    });

    test('a failed refresh keeps the data already on screen', () async {
      service.ledger = ledger(2);
      final controller = PointsController(service, PointsView.overview);
      await controller.load();
      service.entryFailures.add(offlineFailure);
      await controller.refresh();
      expect(controller.phase, PointsPhase.ready);
      expect(controller.refreshError, isNotNull);
      expect(controller.entries, hasLength(2));
      await controller.refresh();
      expect(controller.refreshError, isNull);
    });
  });

  group('single entry', () {
    test('loads the entry and the source title when it can', () async {
      service.ledger = [ledgerEntry(1, video: videoId)];
      final controller = PointsEntryController(service, entryId(1),
          videoTitle: (id) async => id == videoId ? 'Waterside at dawn' : null);
      await controller.load();
      expect(controller.phase, PointsEntryPhase.ready);
      expect(controller.sourceTitle, 'Waterside at dawn');
    });

    test('a title failure never fails the entry', () async {
      service.ledger = [ledgerEntry(1, video: videoId)];
      final controller = PointsEntryController(service, entryId(1),
          videoTitle: (_) async => throw const ApiFailure(404, 'gone'));
      await controller.load();
      expect(controller.phase, PointsEntryPhase.ready);
      expect(controller.sourceTitle, isNull);
    });

    test('an unknown id is not-found and can be retried', () async {
      final controller = PointsEntryController(service, entryId(9));
      await controller.load();
      expect(controller.phase, PointsEntryPhase.failed);
      expect((controller.error as ApiFailure).kind, FailureKind.notFound);
      service.ledger = [ledgerEntry(9)];
      await controller.load();
      expect(controller.phase, PointsEntryPhase.ready);
    });
  });
}

/// Replays the first page for every request (a misbehaving server).
class _Replaying extends ScriptedPoints {
  _Replaying(ScriptedPoints inner) : super(pageSize: inner.pageSize) {
    ledger = inner.ledger;
    current = inner.current;
  }

  @override
  Future<PointsPage> entries(
      {String? cursor, PointsFilter filter = PointsFilter.all}) async {
    final first = await super.entries(filter: filter);
    return PointsPage(first.items, first.nextCursor);
  }
}

/// A service whose entries cannot be parsed.
class _Unreadable extends ScriptedPoints {
  _Unreadable(ScriptedPoints inner) : super(pageSize: inner.pageSize);

  @override
  Future<PointsPage> entries(
          {String? cursor, PointsFilter filter = PointsFilter.all}) async =>
      throw const FormatException('bad page');
}
