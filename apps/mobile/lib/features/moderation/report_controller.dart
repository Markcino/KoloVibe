import 'package:flutter/foundation.dart';
import '../../core/network/api_client.dart';
import '../discovery/live_video_repository.dart';
import 'live_moderation_repository.dart';

/// A reason the person can pick, and the server code it is sent as. The
/// gateway accepts five codes, so two labels share `harmful`.
class ReportReason {
  const ReportReason(this.label, this.code);
  final String label, code;
}

const reportReasons = [
  ReportReason('Harassment or hateful content', 'harassment'),
  ReportReason('Violence or harmful activity', 'harmful'),
  ReportReason('Sexual or inappropriate content', 'harmful'),
  ReportReason('Rights or ownership concern', 'copyright'),
  ReportReason('Spam or misleading content', 'spam'),
  ReportReason('Something else', 'other'),
];

/// The wording for a reason the server returned. Derived from the code alone,
/// so it is honest where two choices share one code.
String reportReasonLabel(String code) => switch (code) {
      'harassment' => 'Harassment concern',
      'harmful' => 'Harmful content concern',
      'copyright' => 'Rights concern',
      'spam' => 'Spam concern',
      _ => 'Other concern',
    };

enum ReportPhase { loading, failed, ready }

/// Which step of the report the person is on.
enum ReportStage { reason, details, submitted, alreadyReported, error }

/// Drives the report journey (M-071–M-075).
///
/// The server decides everything that matters: whether a report is accepted,
/// whether it duplicates an open one, and what happened to it. The app only
/// sends the choice and shows the answer. Nothing here removes or restricts a
/// video.
class ReportController extends ChangeNotifier {
  ReportController(this._videos, this._moderation, this.videoId,
      {this.lookup = ReportLookup.none, String Function()? newKey})
      : _newKey = newKey ?? LiveModerationRepository.newIdempotencyKey;

  /// What a cold entry should look for before showing a step.
  final ReportLookup lookup;
  final LiveVideoRepository _videos;
  final LiveModerationRepository _moderation;
  final String videoId;
  final String Function() _newKey;

  ReportPhase phase = ReportPhase.loading;
  Object? loadError;
  LiveVideo? video;
  ReportStage stage = ReportStage.reason;
  ReportReason? reason;
  String details = '';
  bool submitting = false;

  /// The server's receipt for a report just sent.
  ModerationReceipt? receipt;

  /// An existing report about this video, when one was found.
  ReportRecord? existing;

  /// Why the last submit was not confirmed.
  Object? submitFailure;

  String? _key;
  String? _keyPayload;
  bool _disposed = false;

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }

  void _emit() {
    if (!_disposed) notifyListeners();
  }

  Future<void> load() async {
    phase = ReportPhase.loading;
    loadError = null;
    _emit();
    try {
      final value = await _videos.detail(videoId);
      if (_disposed) return;
      video = value;
      if (lookup != ReportLookup.none) {
        existing = await _moderation.findReport(videoId,
            openOnly: lookup == ReportLookup.openOnly);
        if (_disposed) return;
        final found = existing;
        if (found != null) {
          stage = lookup == ReportLookup.openOnly
              ? ReportStage.alreadyReported
              : ReportStage.submitted;
        }
      }
      phase = ReportPhase.ready;
    } on ApiFailure catch (failure) {
      loadError = failure;
      phase = ReportPhase.failed;
    } on FormatException {
      loadError = const ApiFailure(
          503, 'The report service returned an unreadable response.');
      phase = ReportPhase.failed;
    }
    _emit();
  }

  void choose(ReportReason value) {
    if (submitting) return;
    reason = value;
    _emit();
  }

  /// M-071 → M-072. A reason is required.
  bool get canContinue => reason != null && !submitting;

  void toDetails() {
    if (!canContinue) return;
    stage = ReportStage.details;
    _emit();
  }

  void setDetails(String value) {
    details = value;
  }

  /// "Return to report details" and "back" from details.
  void backToReason() {
    if (submitting) return;
    stage = ReportStage.reason;
    _emit();
  }

  void backToDetails() {
    if (submitting) return;
    stage = ReportStage.details;
    _emit();
  }

  /// Sends the report. One request at a time. The idempotency key is reused
  /// for an identical retry (so a lost response replays instead of duplicating)
  /// and replaced as soon as the reason or text changes (the server rejects a
  /// reused key with a different body).
  Future<void> submit() async {
    final chosen = reason;
    final current = video;
    if (submitting || chosen == null || current == null) return;
    final text = details.trim();
    final payload = '${chosen.code}\u0000$text';
    if (_key == null || _keyPayload != payload) {
      _key = _newKey();
      _keyPayload = payload;
    }
    submitting = true;
    submitFailure = null;
    _emit();
    try {
      final result = await _moderation.report(
          videoId: current.id, reason: chosen.code, details: text, key: _key!);
      if (_disposed) return;
      receipt = result;
      details = '';
      _key = null;
      stage = ReportStage.submitted;
    } on ApiFailure catch (failure) {
      if (_disposed) return;
      if (LiveModerationRepository.isAlreadyReported(failure)) {
        stage = ReportStage.alreadyReported;
        details = '';
        _key = null;
        submitting = false;
        _emit();
        await _findExisting();
        return;
      }
      if (failure.kind == FailureKind.conflict) _key = null;
      submitFailure = failure;
      stage = ReportStage.error;
    } on FormatException {
      if (_disposed) return;
      // The response could not be trusted, so the report is not confirmed.
      // Keep the key: a retry replays the same report instead of adding one.
      submitFailure =
          const ApiFailure(503, 'The service did not confirm your report.');
      stage = ReportStage.error;
    } finally {
      submitting = false;
    }
    _emit();
  }

  /// Best effort: which report already exists, for the reason shown on M-075.
  Future<void> _findExisting() async {
    try {
      final found = await _moderation.findReport(videoId, openOnly: true);
      if (_disposed) return;
      existing = found;
    } on ApiFailure {
      // The duplicate is still real; only its reason label is missing.
    } on FormatException {
      // Same: show the notice without a reason.
    }
    _emit();
  }
}

/// What a cold entry should look up before showing a step.
enum ReportLookup {
  /// Start a new report.
  none,

  /// M-073: show the latest report about this video, whatever its state.
  latest,

  /// M-075: show an open report about this video.
  openOnly,
}
