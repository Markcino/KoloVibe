import '../../core/network/api_client.dart';
import '../account/live_account_repository.dart';

/// Decision B: the versioned terms, privacy notice and marketing wording, and what this account has accepted.
/// Every answer is parsed strictly; an unexpected shape is refused rather than shown.
const legalKinds = ['terms', 'privacy', 'marketing'];
const requiredLegalKinds = ['terms', 'privacy'];
const legalVersionOutdated = 'legal_version_outdated';

final _version = RegExp(r'^.{1,32}$');
final _date = RegExp(r'^\d{4}-\d{2}-\d{2}$');
final _sha = RegExp(r'^[0-9a-f]{64}$');
final _stamp = RegExp(r'(Z|[+-]\d\d:\d\d)$');

class LegalSummary {
  const LegalSummary(this.kind, this.title, this.version, this.effectiveAt,
      this.pendingLegalReview, this.sha256);
  final String kind, title, version, effectiveAt, sha256;

  /// True until counsel approves the text. The app always says so next to the text.
  final bool pendingLegalReview;

  static LegalSummary parse(Map<String, dynamic> data, {String? kind}) {
    final k = data['kind'], title = data['title'], version = data['version'];
    final effective = data['effective_at'], status = data['status'];
    final sha = data['sha256'];
    if (k is! String ||
        !legalKinds.contains(k) ||
        (kind != null && k != kind) ||
        title is! String ||
        title.isEmpty ||
        title.length > 80 ||
        version is! String ||
        !_version.hasMatch(version) ||
        effective is! String ||
        !_date.hasMatch(effective) ||
        (status != 'pending_legal_review' && status != 'approved') ||
        sha is! String ||
        !_sha.hasMatch(sha)) {
      throw const FormatException('Invalid legal document');
    }
    return LegalSummary(
        k, title, version, effective, status == 'pending_legal_review', sha);
  }
}

class LegalDocument {
  const LegalDocument(this.summary, this.text);
  final LegalSummary summary;
  final String text;

  factory LegalDocument.fromJson(Map<String, dynamic> data, String kind) {
    final text = data['text'];
    if (data.length != 7 ||
        text is! String ||
        text.isEmpty ||
        text.length > 32768) {
      throw const FormatException('Invalid legal document');
    }
    return LegalDocument(LegalSummary.parse(data, kind: kind), text);
  }
}

class LegalRecord {
  const LegalRecord(this.summary, this.acceptedVersion, this.acceptedAt);
  final LegalSummary summary;
  final String? acceptedVersion;
  final DateTime? acceptedAt;
}

class LegalState {
  const LegalState(this.documents, this.acceptanceRequired,
      this.marketingGranted, this.marketingVersion);
  final List<LegalRecord> documents;
  final bool acceptanceRequired;
  final bool marketingGranted;
  final String marketingVersion;

  Map<String, String> get currentVersions => {
        for (final record in documents)
          record.summary.kind: record.summary.version
      };

  factory LegalState.fromJson(Map<String, dynamic> data) {
    final documents = data['documents'], required = data['acceptance_required'];
    final marketing = data['marketing'];
    if (data.length != 3 ||
        documents is! List ||
        documents.length != 2 ||
        required is! bool ||
        marketing is! Map<String, dynamic> ||
        marketing.length != 3) {
      throw const FormatException('Invalid legal state');
    }
    final records = <LegalRecord>[];
    for (final (index, item) in documents.indexed) {
      if (item is! Map<String, dynamic> || item.length != 8) {
        throw const FormatException('Invalid legal state');
      }
      final accepted = item['accepted_version'], at = item['accepted_at'];
      if ((accepted != null &&
              (accepted is! String || !_version.hasMatch(accepted))) ||
          (at != null && (at is! String || !_stamp.hasMatch(at)))) {
        throw const FormatException('Invalid legal state');
      }
      records.add(LegalRecord(
          LegalSummary.parse(item, kind: requiredLegalKinds[index]),
          accepted as String?,
          at == null ? null : DateTime.parse(at as String)));
    }
    final granted = marketing['granted'], version = marketing['version'];
    final updated = marketing['updated_at'];
    if (granted is! bool ||
        version is! String ||
        !_version.hasMatch(version) ||
        (updated != null &&
            (updated is! String || !_stamp.hasMatch(updated)))) {
      throw const FormatException('Invalid legal state');
    }
    return LegalState(records, required, granted, version);
  }
}

class LiveLegalRepository {
  const LiveLegalRepository(this.account);
  final LiveAccountRepository account;

  /// Public: readable before registration.
  Future<LegalDocument> document(String kind) async {
    if (!legalKinds.contains(kind)) throw ArgumentError('Unknown document');
    return LegalDocument.fromJson(
        await account.api.request('/legal/$kind'), kind);
  }

  Future<LegalState> state() async =>
      LegalState.fromJson(await account.authenticatedRequest('/me/legal'));

  /// Accept exactly the versions that were shown. A 409 `legal_version_outdated` means the text changed meanwhile.
  Future<LegalState> accept(Map<String, String> versions) async {
    if (versions.isEmpty ||
        !versions.keys.every(requiredLegalKinds.contains) ||
        !versions.values.every(_version.hasMatch)) {
      throw ArgumentError('Invalid acceptance');
    }
    return LegalState.fromJson(await account.authenticatedRequest('/me/legal',
        method: 'POST', body: {'accepted': versions}));
  }

  Future<LegalState> setMarketing(bool granted, String version) async {
    if (!_version.hasMatch(version)) throw ArgumentError('Invalid version');
    return LegalState.fromJson(await account.authenticatedRequest(
        '/me/marketing-consent',
        method: 'PUT',
        body: {'granted': granted, 'version': version}));
  }
}

bool isOutdatedLegalVersion(Object error) =>
    error is ApiFailure &&
    error.status == 409 &&
    error.code == legalVersionOutdated;
