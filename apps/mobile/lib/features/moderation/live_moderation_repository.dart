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
    if (timestamp == null) {
      throw const FormatException('Invalid moderation date');
    }
    return ModerationReceipt(id, videoId, status, timestamp);
  }
}

/// The five reasons the gateway accepts for a report.
const reportReasonCodes = {
  'spam',
  'harassment',
  'copyright',
  'harmful',
  'other'
};

/// One of the caller's own reports, as listed by `GET /me/reports`.
class ReportRecord {
  const ReportRecord(
      this.id, this.videoId, this.status, this.createdAt, this.reason);
  final String id, videoId, status, reason;
  final DateTime createdAt;

  bool get isOpen => status == 'open';

  factory ReportRecord.fromJson(Object? value) {
    const keys = {
      'id',
      'video_id',
      'status',
      'created_at',
      'reason',
      'details'
    };
    if (value is! Map<String, dynamic> ||
        value.keys.toSet().difference(keys).isNotEmpty ||
        !value.keys.toSet().containsAll(keys)) {
      throw const FormatException('Invalid report record');
    }
    // Validate the shared receipt fields with the receipt parser.
    final receipt = ModerationReceipt.fromJson({
      'id': value['id'],
      'video_id': value['video_id'],
      'status': value['status'],
      'created_at': value['created_at'],
    });
    final reason = value['reason'];
    if (reason is! String ||
        !reportReasonCodes.contains(reason) ||
        value['details'] is! String) {
      throw const FormatException('Invalid report record');
    }
    return ReportRecord(
        receipt.id, receipt.videoId, receipt.status, receipt.createdAt, reason);
  }
}

class ReportPage {
  const ReportPage(this.items, this.nextCursor);
  final List<ReportRecord> items;
  final String? nextCursor;
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
        !reportReasonCodes.contains(reason) ||
        details.length > 2000 ||
        !RegExp(r'^[A-Za-z0-9_-]{16,128}$').hasMatch(key)) {
      throw const FormatException('Invalid report');
    }
    final data = await account.authenticatedRequest('/reports',
        method: 'POST',
        idempotencyKey: key,
        body: {'video_id': videoId, 'reason': reason, 'details': details});
    final receipt = ModerationReceipt.fromJson(data);
    if (receipt.videoId != videoId) {
      throw const FormatException('Mismatched report');
    }
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
    if (receipt.videoId != videoId) {
      throw const FormatException('Mismatched appeal');
    }
    return receipt;
  }

  /// One page (at most 20) of the caller's own reports, newest first.
  Future<ReportPage> ownReports({String? cursor}) async {
    if (cursor != null && !isApiId(cursor)) {
      throw const FormatException('Invalid cursor');
    }
    final data = await account.authenticatedRequest('/me/reports',
        query: {if (cursor != null) 'cursor': cursor});
    final items = data['items'];
    final next = data['next_cursor'];
    if (items is! List ||
        items.length > 20 ||
        data.keys.toSet().difference({'items', 'next_cursor'}).isNotEmpty ||
        !data.containsKey('next_cursor')) {
      throw const FormatException('Invalid report list');
    }
    final records = items.map(ReportRecord.fromJson).toList(growable: false);
    if (records.map((r) => r.id).toSet().length != records.length ||
        next != null &&
            (next is! String ||
                !isApiId(next) ||
                records.isEmpty ||
                records.last.id != next ||
                next == cursor)) {
      throw const FormatException('Invalid report cursor');
    }
    return ReportPage(records, next as String?);
  }

  /// The caller's most recent report about [videoId], or null when none is
  /// found within [maxPages] pages. With [openOnly] it looks for an open one,
  /// which is what makes a new report a duplicate.
  Future<ReportRecord?> findReport(String videoId,
      {bool openOnly = false, int maxPages = 5}) async {
    if (!isApiId(videoId)) throw const FormatException('Invalid video');
    String? cursor;
    for (var page = 0; page < maxPages; page++) {
      final result = await ownReports(cursor: cursor);
      for (final record in result.items) {
        if (record.videoId == videoId && (!openOnly || record.isOpen)) {
          return record;
        }
      }
      cursor = result.nextCursor;
      if (cursor == null) return null;
    }
    return null;
  }

  /// True when [error] is the gateway's "you already have an open report".
  static bool isAlreadyReported(Object error) =>
      error is ApiFailure &&
      error.status == 409 &&
      error.code == 'already_reported';
  Future<List<ModerationReceipt>> ownAppeals({String? cursor}) =>
      _own('appeals', cursor);

  Future<List<ModerationReceipt>> _own(String kind, String? cursor) async {
    if (cursor != null && !isApiId(cursor)) {
      throw const FormatException('Invalid cursor');
    }
    final data = await account.authenticatedRequest('/me/$kind',
        query: {if (cursor != null) 'cursor': cursor});
    final items = data['items'];
    if (items is! List ||
        items.length > 20 ||
        !data.containsKey('next_cursor')) {
      throw const FormatException('Invalid moderation list');
    }
    return items.map((item) {
      if (item is! Map<String, dynamic>) {
        throw const FormatException('Invalid moderation item');
      }
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
