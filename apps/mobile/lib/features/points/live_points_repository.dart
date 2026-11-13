import '../../core/network/api_client.dart';
import '../account/live_account_repository.dart';

/// Read-only view of the creator's Lone Stars ledger.
///
/// Every figure is owned by the server (DEC-003). The app never awards,
/// adjusts, estimates or sums points: it parses and displays what the gateway
/// returns. This file deliberately has no write method.

/// Server-side status filters accepted by `GET /creators/me/points/entries`.
/// `withheld` is not a server filter: withheld receipts appear only in `all`.
enum PointsFilter {
  all('all'),
  confirmed('confirmed'),
  pending('pending'),
  adjustments('adjustments');

  const PointsFilter(this.query);
  final String query;
}

/// Entry statuses the gateway can return.
const pointsStatuses = {'confirmed', 'pending', 'withheld', 'adjustments'};

class PointsBalance {
  const PointsBalance(this.creatorId, this.balance, this.asOf,
      {required this.confirmed,
      required this.pending,
      required this.withheld,
      required this.reversed});
  final String creatorId;

  /// The server's net ledger total (awards, reversals and adjustments).
  final int balance;
  final DateTime asOf;

  /// Server-derived category totals; the app never recomputes them.
  final int confirmed, pending, withheld, reversed;

  factory PointsBalance.fromJson(Map<String, dynamic> value) {
    const keys = {
      'creator_id',
      'balance',
      'currency',
      'as_of',
      'confirmed',
      'pending',
      'withheld',
      'reversed'
    };
    final creatorId = value['creator_id'];
    final amount = value['balance'];
    final at = value['as_of'];
    final totals = [
      for (final key in ['confirmed', 'pending', 'withheld', 'reversed'])
        value[key]
    ];
    if (value.keys.toSet().difference(keys).isNotEmpty ||
        creatorId is! String ||
        !isApiId(creatorId) ||
        amount is! int ||
        value['currency'] != 'POINTS' ||
        at is! String ||
        totals.any((total) => total is! int || total < 0)) {
      throw const FormatException('Invalid points balance');
    }
    final asOf = DateTime.tryParse(at);
    if (asOf == null) throw const FormatException('Invalid points balance');
    return PointsBalance(creatorId, amount, asOf,
        confirmed: totals[0] as int,
        pending: totals[1] as int,
        withheld: totals[2] as int,
        reversed: totals[3] as int);
  }
}

class PointsEntry {
  const PointsEntry(this.id, this.creatorId, this.amount, this.kind,
      this.createdAt, this.status, this.videoId);
  final String id, creatorId, kind, status;
  final int amount;
  final DateTime createdAt;

  /// The source video, when the ledger recorded one.
  final String? videoId;

  bool get isWithheld => status == 'withheld';
  bool get isPending => status == 'pending';
  bool get isReversal => kind == 'reversal';

  factory PointsEntry.fromJson(Map<String, dynamic> value) {
    const keys = {
      'id',
      'creator_id',
      'amount',
      'kind',
      'rule_version',
      'created_at',
      'status',
      'video_id'
    };
    final id = value['id'];
    final creatorId = value['creator_id'];
    final amount = value['amount'];
    final kind = value['kind'];
    final at = value['created_at'];
    final status = value['status'];
    final videoId = value['video_id'];
    final rule = value['rule_version'];
    if (value.keys.toSet().difference(keys).isNotEmpty ||
        id is! String ||
        !isApiId(id) ||
        creatorId is! String ||
        !isApiId(creatorId) ||
        amount is! int ||
        amount == 0 ||
        at is! String ||
        kind is! String ||
        !{'award', 'reversal', 'adjustment'}.contains(kind) ||
        status is! String ||
        !pointsStatuses.contains(status) ||
        // Mirrors the gateway: only reversals and adjustments are
        // "adjustments", and awards are positive, reversals negative.
        (status == 'adjustments') != (kind != 'award') ||
        kind == 'award' && amount < 0 ||
        kind == 'reversal' && amount > 0 ||
        videoId != null && (videoId is! String || !isApiId(videoId)) ||
        rule is! String ||
        rule.isEmpty ||
        rule.length > 32) {
      throw const FormatException('Invalid points entry');
    }
    final createdAt = DateTime.tryParse(at);
    if (createdAt == null) throw const FormatException('Invalid points entry');
    return PointsEntry(
        id, creatorId, amount, kind, createdAt, status, videoId as String?);
  }
}

class PointsPage {
  const PointsPage(this.items, this.nextCursor);
  final List<PointsEntry> items;
  final String? nextCursor;
}

class LivePointsRepository {
  const LivePointsRepository(this.account);
  final LiveAccountRepository account;

  Future<PointsBalance> balance() async => PointsBalance.fromJson(
      await account.authenticatedRequest('/creators/me/points'));

  /// One page (at most 20) of the creator's ledger, newest first.
  Future<PointsPage> entries(
      {String? cursor, PointsFilter filter = PointsFilter.all}) async {
    if (cursor != null && !isApiId(cursor)) {
      throw const FormatException('Invalid points cursor');
    }
    final result = await account.authenticatedRequest(
      '/creators/me/points/entries',
      query: {
        if (cursor != null) 'cursor': cursor,
        if (filter != PointsFilter.all) 'status': filter.query,
      },
    );
    final raw = result['items'];
    final next = result['next_cursor'];
    if (raw is! List ||
        raw.length > 20 ||
        result.keys.toSet().difference({'items', 'next_cursor'}).isNotEmpty ||
        !result.containsKey('next_cursor')) {
      throw const FormatException('Invalid points page');
    }
    final items = raw.map((value) {
      if (value is! Map<String, dynamic>) {
        throw const FormatException('Invalid points entry');
      }
      return PointsEntry.fromJson(value);
    }).toList(growable: false);
    if (items.map((item) => item.id).toSet().length != items.length ||
        items.any((item) => !_matches(filter, item)) ||
        next != null &&
            (next is! String ||
                !isApiId(next) ||
                items.length != 20 ||
                next != items.last.id ||
                next == cursor)) {
      throw const FormatException('Invalid points cursor');
    }
    return PointsPage(items, next as String?);
  }

  /// One owner-only entry. A foreign or missing id is a 404 from the server.
  Future<PointsEntry> entry(String id) async {
    if (!isApiId(id)) throw const FormatException('Invalid points entry id');
    final entry = PointsEntry.fromJson(
        await account.authenticatedRequest('/creators/me/points/entries/$id'));
    if (entry.id != id) throw const FormatException('Mismatched points entry');
    return entry;
  }

  static bool _matches(PointsFilter filter, PointsEntry item) =>
      filter == PointsFilter.all || item.status == filter.query;
}
