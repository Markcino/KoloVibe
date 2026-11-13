import 'dart:async';

import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/features/points/live_points_repository.dart';

import 'upload_fakes.dart';

const offlineFailure = ApiFailure(
    503, 'The service is unavailable. Please try again.',
    offline: true);
const expiredFailure = ApiFailure(401, 'Session expired');
const notCreator = ApiFailure(403, 'Approved creator required');

/// A deterministic UUID for ledger row [n].
String entryId(int n) =>
    '00000000-0000-4000-8000-${(0x100000 + n).toRadixString(16).padLeft(12, '0')}';

PointsEntry ledgerEntry(int n,
        {String status = 'confirmed',
        String? kind,
        int? amount,
        String? video,
        String? creator}) =>
    PointsEntry(
        entryId(n),
        creator ?? creatorId,
        amount ?? (status == 'adjustments' ? -20 : 1),
        kind ?? (status == 'adjustments' ? 'reversal' : 'award'),
        DateTime.utc(2026, 10, 28, 12).subtract(Duration(hours: n)),
        status,
        video);

PointsBalance serverBalance(
        {int balance = 1240,
        int pending = 160,
        int withheld = 40,
        int reversed = 20,
        int confirmed = 1260}) =>
    PointsBalance(creatorId, balance, DateTime.utc(2026, 10, 28, 12),
        confirmed: confirmed,
        pending: pending,
        withheld: withheld,
        reversed: reversed);

/// A scripted points service. Mocked: no HTTP.
///
/// [ledger] is newest first. [entries] paginates it like the server does:
/// the cursor is the id of the last row of the previous page, the filter is a
/// status filter, and `withheld` rows appear only under `all`.
class ScriptedPoints extends LivePointsRepository {
  ScriptedPoints({this.pageSize = 20}) : super(unusedAccount());

  final int pageSize;
  PointsBalance current = serverBalance();
  List<PointsEntry> ledger = [];

  Object? balanceFailure;
  final List<Object> entryFailures = [];
  Object? entryFailure;
  Completer<void>? gate;

  int balanceReads = 0;
  final entryReads = <({String? cursor, PointsFilter filter})>[];
  final detailReads = <String>[];

  @override
  Future<PointsBalance> balance() async {
    balanceReads++;
    final failure = balanceFailure;
    if (failure != null) throw failure;
    return current;
  }

  @override
  Future<PointsPage> entries(
      {String? cursor, PointsFilter filter = PointsFilter.all}) async {
    entryReads.add((cursor: cursor, filter: filter));
    final pending = gate;
    if (pending != null) await pending.future;
    if (entryFailures.isNotEmpty) throw entryFailures.removeAt(0);
    final failure = entryFailure;
    if (failure != null) throw failure;
    final rows = ledger
        .where((e) => filter == PointsFilter.all || e.status == filter.query)
        .toList();
    final start =
        cursor == null ? 0 : rows.indexWhere((e) => e.id == cursor) + 1;
    final page = rows.skip(start).take(pageSize).toList();
    final more = start + page.length < rows.length;
    return PointsPage(page, more ? page.last.id : null);
  }

  @override
  Future<PointsEntry> entry(String id) async {
    detailReads.add(id);
    final failure = entryFailure;
    if (failure != null) throw failure;
    final match = ledger.where((e) => e.id == id);
    if (match.isEmpty) throw const ApiFailure(404, 'Not found');
    return match.first;
  }
}
