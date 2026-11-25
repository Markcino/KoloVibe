import '../../core/network/api_client.dart';
import '../account/live_account_repository.dart';

/// Decision F (D-8): measures on the caller's own creator profile.
///
/// The server decides every measure, whether it is active and whether it may
/// be appealed. The app shows the kind, code, policy version and dates it
/// returns; the administrator's private reason is never sent to the app.

const measureKinds = {
  'warning',
  'upload',
  'publishing',
  'monetization',
  'suspension'
};
const measureAppealStatuses = {'open', 'upheld', 'lifted'};

final _reasonCode = RegExp(r'^[A-Z][A-Z0-9_]{1,63}$');
final _policyVersion = RegExp(r'^[A-Za-z0-9._-]{1,32}$');
final _zoned = RegExp(r'(Z|[+-]\d\d:\d\d)$');

DateTime? _timestamp(Object? value, {bool nullable = false}) {
  if (value == null && nullable) return null;
  if (value is! String || !_zoned.hasMatch(value)) {
    throw const FormatException('Invalid measure date');
  }
  final parsed = DateTime.tryParse(value);
  if (parsed == null) throw const FormatException('Invalid measure date');
  return parsed;
}

void _exactKeys(Object? value, Set<String> keys, String what) {
  if (value is! Map<String, dynamic> ||
      value.keys.toSet().difference(keys).isNotEmpty ||
      !value.keys.toSet().containsAll(keys)) {
    throw FormatException('Invalid $what');
  }
}

/// An appeal against one measure, as the server reports it.
class MeasureAppeal {
  const MeasureAppeal(this.id, this.status);
  final String id, status;

  factory MeasureAppeal.fromJson(Object? value) {
    _exactKeys(value, const {'id', 'status'}, 'measure appeal');
    final map = value as Map<String, dynamic>;
    final id = map['id'], status = map['status'];
    if (id is! String ||
        !isApiId(id) ||
        status is! String ||
        !measureAppealStatuses.contains(status)) {
      throw const FormatException('Invalid measure appeal');
    }
    return MeasureAppeal(id, status);
  }
}

class CreatorMeasure {
  const CreatorMeasure(
      {required this.id,
      required this.kind,
      required this.reasonCode,
      required this.policyVersion,
      required this.issuedAt,
      required this.expiresAt,
      required this.liftedAt,
      required this.active,
      required this.appeal});
  final String id, kind, reasonCode, policyVersion;
  final DateTime issuedAt;
  final DateTime? expiresAt, liftedAt;
  final bool active;
  final MeasureAppeal? appeal;

  /// Only an active measure with no appeal yet may be appealed; the server
  /// enforces the same rule and ownership.
  bool get appealable => active && appeal == null;

  factory CreatorMeasure.fromJson(Object? value) {
    const keys = {
      'id',
      'kind',
      'reason_code',
      'policy_version',
      'issued_at',
      'expires_at',
      'lifted_at',
      'active',
      'appeal'
    };
    _exactKeys(value, keys, 'measure');
    final map = value as Map<String, dynamic>;
    final id = map['id'], kind = map['kind'], code = map['reason_code'];
    final version = map['policy_version'], active = map['active'];
    if (id is! String ||
        !isApiId(id) ||
        kind is! String ||
        !measureKinds.contains(kind) ||
        code is! String ||
        !_reasonCode.hasMatch(code) ||
        version is! String ||
        !_policyVersion.hasMatch(version) ||
        active is! bool) {
      throw const FormatException('Invalid measure');
    }
    final liftedAt = _timestamp(map['lifted_at'], nullable: true);
    if (active && liftedAt != null) {
      throw const FormatException('Invalid measure');
    }
    return CreatorMeasure(
        id: id,
        kind: kind,
        reasonCode: code,
        policyVersion: version,
        issuedAt: _timestamp(map['issued_at'])!,
        expiresAt: _timestamp(map['expires_at'], nullable: true),
        liftedAt: liftedAt,
        active: active,
        appeal: map['appeal'] == null
            ? null
            : MeasureAppeal.fromJson(map['appeal']));
  }
}

class OwnMeasures {
  const OwnMeasures(this.creatorId, this.items);

  /// null: no creator profile, and then no measures.
  final String? creatorId;
  final List<CreatorMeasure> items;

  factory OwnMeasures.fromJson(Map<String, dynamic> value) {
    _exactKeys(value, const {'creator_id', 'items'}, 'measures');
    final creator = value['creator_id'], raw = value['items'];
    if (creator != null && (creator is! String || !isApiId(creator)) ||
        raw is! List ||
        raw.length > 50) {
      throw const FormatException('Invalid measures');
    }
    final items = raw.map(CreatorMeasure.fromJson).toList(growable: false);
    if (items.map((item) => item.id).toSet().length != items.length ||
        creator == null && items.isNotEmpty) {
      throw const FormatException('Invalid measures');
    }
    return OwnMeasures(creator as String?, items);
  }
}

class LiveRestrictionRepository {
  const LiveRestrictionRepository(this.account);
  final LiveAccountRepository account;

  /// `GET /creators/me/restrictions`.
  Future<OwnMeasures> mine() async => OwnMeasures.fromJson(
      await account.authenticatedRequest('/creators/me/restrictions'));

  /// `POST /creators/me/restrictions/{id}/appeals`. Repeating the same reason
  /// answers the existing appeal.
  Future<MeasureAppeal> appeal(
      {required String measureId, required String reason}) async {
    final trimmed = reason.trim();
    if (!isApiId(measureId) || trimmed.length < 10 || reason.length > 2000) {
      throw const FormatException('Invalid appeal');
    }
    return MeasureAppeal.fromJson(await account.authenticatedRequest(
        '/creators/me/restrictions/$measureId/appeals',
        method: 'POST',
        body: {'reason': trimmed}));
  }
}

/// What a measure blocks, in plain words.
String measureKindLabel(String kind) => switch (kind) {
      'warning' => 'Warning',
      'upload' => 'Uploads paused',
      'publishing' => 'Publishing paused',
      'monetization' => 'Earnings paused',
      'suspension' => 'Creator account suspended',
      _ => 'Measure',
    };

String measureKindEffect(String kind) => switch (kind) {
      'warning' => 'Nothing is blocked. Please review the policy named here.',
      'upload' => 'You can’t upload new videos while this applies.',
      'publishing' => 'You can’t publish videos while this applies.',
      'monetization' => 'Future earnings are paused while this applies.',
      'suspension' => 'You can’t upload, publish or earn while this applies.',
      _ => '',
    };

String measureAppealLabel(String status) => switch (status) {
      'open' => 'Appeal under review',
      'upheld' => 'Appeal reviewed: measure kept',
      'lifted' => 'Appeal reviewed: measure lifted',
      _ => 'Appeal',
    };
