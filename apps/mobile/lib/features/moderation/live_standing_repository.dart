import '../../core/network/api_client.dart';
import '../account/live_account_repository.dart';

/// Read-only access to the caller's own moderation notices and standing.
///
/// The server owns every decision, reason and eligibility flag. The app
/// parses and shows them; it never infers a decision or an appeal right.

const noticeDecisions = {
  'none',
  'rejected',
  'removed',
  'restricted',
  'restored'
};
const appealStatuses = {'open', 'denied', 'restored'};
const creatorStatuses = {'pending', 'active', 'restricted', 'suspended'};

final _reasonCode = RegExp(r'^[A-Z][A-Z0-9_]{1,63}$');
final _zoned = RegExp(r'(Z|[+-]\d\d:\d\d)$');

DateTime _timestamp(Object? value, String what) {
  if (value is! String || !_zoned.hasMatch(value)) {
    throw FormatException('Invalid $what');
  }
  final parsed = DateTime.tryParse(value);
  if (parsed == null) throw FormatException('Invalid $what');
  return parsed;
}

/// The caller's own review request for a removal.
class OwnAppeal {
  const OwnAppeal(this.id, this.status, this.createdAt, this.reason);
  final String id, status, reason;
  final DateTime createdAt;

  factory OwnAppeal.fromJson(Object? value, String videoId) {
    const keys = {'id', 'video_id', 'status', 'created_at', 'reason'};
    if (value is! Map<String, dynamic> ||
        value.keys.toSet().difference(keys).isNotEmpty ||
        !value.keys.toSet().containsAll(keys)) {
      throw const FormatException('Invalid appeal');
    }
    final id = value['id'], status = value['status'], reason = value['reason'];
    if (id is! String ||
        !isApiId(id) ||
        value['video_id'] != videoId ||
        status is! String ||
        !appealStatuses.contains(status) ||
        reason is! String ||
        reason.length < 10 ||
        reason.length > 2000) {
      throw const FormatException('Invalid appeal');
    }
    return OwnAppeal(
        id, status, _timestamp(value['created_at'], 'appeal date'), reason);
  }
}

/// The latest applied decision about one of the caller's videos.
class VideoNotice {
  const VideoNotice(this.videoId, this.decision, this.reasonCode,
      this.decidedAt, this.appealable, this.appeal);
  final String videoId, decision;
  final String? reasonCode;
  final DateTime? decidedAt;

  /// The server's answer to "may a review be requested?". Never inferred.
  final bool appealable;
  final OwnAppeal? appeal;

  bool get hasDecision => decision != 'none';

  factory VideoNotice.fromJson(Object? value) {
    const keys = {
      'video_id',
      'decision',
      'reason_code',
      'decided_at',
      'appealable',
      'appeal'
    };
    if (value is! Map<String, dynamic> ||
        value.keys.toSet().difference(keys).isNotEmpty ||
        !value.keys.toSet().containsAll(keys)) {
      throw const FormatException('Invalid notice');
    }
    final videoId = value['video_id'], decision = value['decision'];
    final code = value['reason_code'], appealable = value['appealable'];
    if (videoId is! String ||
        !isApiId(videoId) ||
        decision is! String ||
        !noticeDecisions.contains(decision) ||
        appealable is! bool ||
        code != null && (code is! String || !_reasonCode.hasMatch(code))) {
      throw const FormatException('Invalid notice');
    }
    final decidedAt = value['decided_at'] == null
        ? null
        : _timestamp(value['decided_at'], 'notice date');
    if (decision != 'none' && decidedAt == null) {
      throw const FormatException('Invalid notice');
    }
    final appeal = value['appeal'] == null
        ? null
        : OwnAppeal.fromJson(value['appeal'], videoId);
    // Mirrors the gateway: only a removal with no appeal yet is appealable.
    if (appealable && (decision != 'removed' || appeal != null)) {
      throw const FormatException('Invalid notice');
    }
    return VideoNotice(
        videoId, decision, code as String?, decidedAt, appealable, appeal);
  }
}

/// Account and creator standing with up to 20 recent notices.
class AccountStanding {
  const AccountStanding(
      this.creatorStatus, this.publishingAllowed, this.notices);

  /// null: no creator profile.
  final String? creatorStatus;
  final bool publishingAllowed;
  final List<VideoNotice> notices;

  factory AccountStanding.fromJson(Map<String, dynamic> value) {
    const keys = {
      'account_status',
      'creator_status',
      'publishing_allowed',
      'notices'
    };
    if (value.keys.toSet().difference(keys).isNotEmpty ||
        !value.keys.toSet().containsAll(keys)) {
      throw const FormatException('Invalid standing');
    }
    final creator = value['creator_status'],
        allowed = value['publishing_allowed'];
    final raw = value['notices'];
    if (value['account_status'] != 'active' ||
        creator != null &&
            (creator is! String || !creatorStatuses.contains(creator)) ||
        allowed is! bool ||
        allowed && creator != 'active' ||
        raw is! List ||
        raw.length > 20) {
      throw const FormatException('Invalid standing');
    }
    final notices = raw.map(VideoNotice.fromJson).toList(growable: false);
    if (notices.map((n) => n.videoId).toSet().length != notices.length) {
      throw const FormatException('Invalid standing');
    }
    return AccountStanding(creator as String?, allowed, notices);
  }
}

class LiveStandingRepository {
  const LiveStandingRepository(this.account);
  final LiveAccountRepository account;

  /// `GET /creators/me/videos/{id}/notice` (owner creator only).
  Future<VideoNotice> notice(String videoId) async {
    if (!isApiId(videoId)) throw const FormatException('Invalid video');
    final notice = VideoNotice.fromJson(await account
        .authenticatedRequest('/creators/me/videos/$videoId/notice'));
    if (notice.videoId != videoId) {
      throw const FormatException('Mismatched notice');
    }
    return notice;
  }

  /// `GET /me/standing`.
  Future<AccountStanding> standing() async => AccountStanding.fromJson(
      await account.authenticatedRequest('/me/standing'));
}
