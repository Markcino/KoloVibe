import '../../core/network/api_client.dart';
import '../account/live_account_repository.dart';

class PointsBalance {
  const PointsBalance(this.creatorId, this.balance, this.asOf);
  final String creatorId;
  final int balance;
  final DateTime asOf;

  factory PointsBalance.fromJson(Map<String, dynamic> value) {
    final creatorId = value['creator_id'];
    final amount = value['balance'];
    final at = value['as_of'];
    if (creatorId is! String ||
        !isApiId(creatorId) ||
        amount is! int ||
        value['currency'] != 'POINTS' ||
        at is! String) {
      throw const FormatException('Invalid points balance');
    }
    return PointsBalance(creatorId, amount, DateTime.parse(at));
  }
}

class PointsEntry {
  const PointsEntry(
      this.id, this.creatorId, this.amount, this.kind, this.createdAt);
  final String id, creatorId, kind;
  final int amount;
  final DateTime createdAt;

  factory PointsEntry.fromJson(Map<String, dynamic> value) {
    final id = value['id'];
    final creatorId = value['creator_id'];
    final amount = value['amount'];
    final kind = value['kind'];
    final at = value['created_at'];
    if (id is! String ||
        !isApiId(id) ||
        creatorId is! String ||
        !isApiId(creatorId) ||
        amount is! int ||
        at is! String ||
        kind is! String ||
        !{'award', 'reversal', 'adjustment'}.contains(kind) ||
        value['rule_version'] is! String) {
      throw const FormatException('Invalid points entry');
    }
    return PointsEntry(id, creatorId, amount, kind, DateTime.parse(at));
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

  Future<PointsPage> entries({String? cursor}) async {
    if (cursor != null && !isApiId(cursor)) {
      throw const FormatException('Invalid points cursor');
    }
    final result = await account.authenticatedRequest(
      '/creators/me/points/entries',
      query: {if (cursor != null) 'cursor': cursor},
    );
    final raw = result['items'];
    final next = result['next_cursor'];
    if (raw is! List || raw.length > 20 || !result.containsKey('next_cursor')) {
      throw const FormatException('Invalid points page');
    }
    final items = raw.map((value) {
      if (value is! Map<String, dynamic>) {
        throw const FormatException('Invalid points entry');
      }
      return PointsEntry.fromJson(value);
    }).toList(growable: false);
    if (items.map((item) => item.id).toSet().length != items.length ||
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
}
