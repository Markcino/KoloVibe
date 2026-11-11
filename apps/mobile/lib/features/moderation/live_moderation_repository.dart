import 'dart:convert';
import 'dart:math';
import '../../core/network/api_client.dart';
import '../account/live_account_repository.dart';

class ModerationReceipt {
  const ModerationReceipt(this.id, this.videoId, this.status, this.createdAt);
  final String id, videoId, status;
  final DateTime createdAt;

  factory ModerationReceipt.fromJson(Object? value) {
    if (value is! Map<String, dynamic> ||
        value.keys.toSet().difference(
            {'id', 'video_id', 'status', 'created_at'}).isNotEmpty) {
      throw const FormatException('Invalid moderation receipt');
    }
    final id = value['id'], videoId = value['video_id'];
    final status = value['status'], created = value['created_at'];
    if (id is! String ||
        !isApiId(id) ||
        videoId is! String ||
        !isApiId(videoId) ||
        status is! String ||
        !{'open', 'dismissed', 'resolved', 'denied', 'restored'}
            .contains(status) ||
        created is! String) {
      throw const FormatException('Invalid moderation receipt');
    }
    final timestamp = DateTime.tryParse(created);
    if (timestamp == null)
      throw const FormatException('Invalid moderation date');
    return ModerationReceipt(id, videoId, status, timestamp);
  }
}

class LiveModerationRepository {
  const LiveModerationRepository(this.account);
  final LiveAccountRepository account;

  Future<ModerationReceipt> report(
      {required String videoId,
      required String reason,
      required String details,
      required String key}) async {
    if (!isApiId(videoId) ||
        !{'spam', 'harassment', 'copyright', 'harmful', 'other'}
            .contains(reason) ||
        details.length > 2000 ||
        !RegExp(r'^[A-Za-z0-9_-]{16,128}$').hasMatch(key)) {
      throw const FormatException('Invalid report');
    }
    final data = await account.authenticatedRequest('/reports',
        method: 'POST',
        idempotencyKey: key,
        body: {'video_id': videoId, 'reason': reason, 'details': details});
    final receipt = ModerationReceipt.fromJson(data);
    if (receipt.videoId != videoId)
      throw const FormatException('Mismatched report');
    return receipt;
  }

  Future<ModerationReceipt> appeal(
      {required String videoId, required String reason}) async {
    if (!isApiId(videoId) ||
        reason.trim().length < 10 ||
        reason.length > 2000) {
      throw const FormatException('Invalid appeal');
    }
    final data = await account.authenticatedRequest('/videos/$videoId/appeals',
        method: 'POST', body: {'reason': reason.trim()});
    final receipt = ModerationReceipt.fromJson(data);
    if (receipt.videoId != videoId)
      throw const FormatException('Mismatched appeal');
    return receipt;
  }

  Future<List<ModerationReceipt>> ownReports({String? cursor}) =>
      _own('reports', cursor);
  Future<List<ModerationReceipt>> ownAppeals({String? cursor}) =>
      _own('appeals', cursor);

  Future<List<ModerationReceipt>> _own(String kind, String? cursor) async {
    if (cursor != null && !isApiId(cursor))
      throw const FormatException('Invalid cursor');
    final data = await account.authenticatedRequest('/me/$kind',
        query: {if (cursor != null) 'cursor': cursor});
    final items = data['items'];
    if (items is! List ||
        items.length > 20 ||
        !data.containsKey('next_cursor')) {
      throw const FormatException('Invalid moderation list');
    }
    return items.map((item) {
      if (item is! Map<String, dynamic>)
        throw const FormatException('Invalid moderation item');
      return ModerationReceipt.fromJson({
        'id': item['id'],
        'video_id': item['video_id'],
        'status': item['status'],
        'created_at': item['created_at'],
      });
    }).toList(growable: false);
  }

  static String newIdempotencyKey() {
    final random = Random.secure();
    return base64Url
        .encode(List<int>.generate(24, (_) => random.nextInt(256)))
        .replaceAll('=', '');
  }
}
