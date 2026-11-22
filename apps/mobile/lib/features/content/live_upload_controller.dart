import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:flutter/foundation.dart';
import 'package:image_picker/image_picker.dart';
import '../../core/network/api_client.dart';
import '../creators/live_creator_onboarding_repository.dart';
import 'live_content_repository.dart';

/// Where the creator is in the upload journey (M-041–M-049).
enum UploadPhase {
  /// Eligibility is being read (M-041 gate).
  checkingAccess,

  /// Eligibility could not be read; retry is available.
  accessFailed,

  /// The account is not an approved creator.
  ineligible,

  /// The session expired; sign in again before uploading.
  signedOut,

  /// The server refused the action for this account (restriction or role).
  restricted,

  /// File selection and story details (M-041–M-044).
  editing,

  /// Draft, reservation, transfer or completion in flight (M-046).
  uploading,

  /// A retryable interruption before the server confirmed receipt (M-047).
  interrupted,

  /// The server reported a failed upload or preparation (M-048).
  failed,

  /// Received; the server is preparing the video (M-049).
  preparing,

  /// Preparation ended in an owner-visible state (review, published, ...).
  settled,
}

/// The step that was running when an interruption happened, used to resume.
enum _Step { draft, reserve, transfer, complete }

typedef UploadDelay = Future<void> Function(Duration duration);

class UploadDetails {
  const UploadDetails(this.title, this.description, this.category, this.tags);
  final String title, description, category;
  final List<String> tags;
}

/// Field-level validation errors keyed by field name.
class DetailsErrors {
  const DetailsErrors(this.fields);
  final Map<String, String> fields;
  bool get isEmpty => fields.isEmpty;
}

DetailsErrors validateUploadDetails(
    String title, String description, String? category, String hashtags) {
  final errors = <String, String>{};
  final cleaned = title.trim();
  if (cleaned.isEmpty) {
    errors['title'] = 'Enter a title.';
  } else if (cleaned.length > 160) {
    errors['title'] = 'Use 160 characters or fewer.';
  }
  if (description.length > 2000) {
    errors['description'] = 'Use 2,000 characters or fewer.';
  }
  if (category == null || !videoCategories.containsKey(category)) {
    errors['category'] = 'Select a category to continue.';
  }
  try {
    normalizeTags(hashtags.split(RegExp(r'[\s,]+')));
  } on FormatException catch (failure) {
    errors['tags'] = failure.message == 'Too many hashtags'
        ? 'Use up to five hashtags.'
        : 'Hashtags use letters, numbers and underscores, up to 30 characters.';
  }
  return DetailsErrors(errors);
}

class LiveUploadController extends ChangeNotifier {
  LiveUploadController(this.content, this.onboarding,
      {UploadDelay? delay,
      this.pollSchedule = const [3, 5, 8, 13, 20],
      this.maxPolls = 18})
      : _delay = delay ?? Future<void>.delayed;

  final LiveContentRepository content;
  final LiveCreatorOnboardingRepository onboarding;
  final UploadDelay _delay;

  /// Seconds between status reads; the last entry repeats up to [maxPolls].
  final List<int> pollSchedule;
  final int maxPolls;

  UploadPhase phase = UploadPhase.checkingAccess;
  XFile? selected;
  int? selectedBytes;
  OwnedVideo? draft;
  VideoUploadStatus? status;
  String? error;
  DetailsErrors detailsErrors = const DetailsErrors({});

  /// Bytes accepted by the transfer so far; null when no transfer is running.
  int? sentBytes;

  /// True when polling stopped before the server reported a final state.
  bool stalePreparation = false;
  bool originalityAccepted = false;

  bool _disposed = false;
  int _generation = 0;
  String? _draftKey;
  String? _uploadKey;
  UploadIntent? _intent;
  UploadDetails? _details;
  _Step _step = _Step.draft;

  bool get busy =>
      phase == UploadPhase.checkingAccess || phase == UploadPhase.uploading;
  bool get canPickFile =>
      phase == UploadPhase.editing && draft == null ||
      phase == UploadPhase.failed ||
      phase == UploadPhase.interrupted && _step != _Step.complete;

  /// 0–1 transfer progress, or null when it is not measurable.
  double? get progress {
    final sent = sentBytes;
    final total = selectedBytes;
    if (sent == null || total == null || total == 0) return null;
    return (sent / total).clamp(0, 1).toDouble();
  }

  void _update() {
    if (!_disposed) notifyListeners();
  }

  String _key() {
    final random = Random.secure();
    return base64Url.encode(List<int>.generate(24, (_) => random.nextInt(256)));
  }

  void _classify(Object failure, {required UploadPhase fallback}) {
    if (failure is ApiFailure) {
      switch (failure.kind) {
        case FailureKind.expired:
          phase = UploadPhase.signedOut;
          error = 'Your session has ended. Sign in again to continue.';
        case FailureKind.forbidden:
          phase = UploadPhase.restricted;
          error = 'Uploading is not available for this account right now.';
        case FailureKind.conflict:
          // A rejected reservation must be replaced with a fresh key.
          _uploadKey = null;
          phase = fallback;
          error = failure.message;
        case FailureKind.invalid:
          phase = UploadPhase.failed;
          error = failure.message;
        case FailureKind.offline:
        case FailureKind.rateLimited:
        case FailureKind.notFound:
        case FailureKind.unavailable:
          phase = fallback;
          error = failure.offline
              ? 'You appear to be offline. Reconnect, then try again.'
              : failure.message;
      }
    } else if (failure is FormatException) {
      phase = UploadPhase.failed;
      error = failure.message;
    } else {
      phase = fallback;
      error = 'The upload was interrupted. Try again.';
    }
  }

  Future<void> checkEligibility() async {
    if (phase == UploadPhase.uploading) return;
    phase = UploadPhase.checkingAccess;
    error = null;
    _update();
    try {
      final eligibility = await onboarding.eligibility();
      if (_disposed) return;
      phase =
          eligibility.eligible ? UploadPhase.editing : UploadPhase.ineligible;
    } on ApiFailure catch (failure) {
      _classify(failure, fallback: UploadPhase.accessFailed);
    } on FormatException {
      phase = UploadPhase.accessFailed;
      error = 'Creator eligibility could not be read.';
    } finally {
      _update();
    }
  }

  /// Checks the file locally (M-043). The server still validates codec,
  /// duration and resolution during processing.
  Future<void> select(XFile file) async {
    if (!canPickFile) return;
    error = null;
    _update();
    try {
      final size = await file.length();
      if (!file.name.toLowerCase().endsWith('.mp4') ||
          size < 12 ||
          size > 50 * 1024 * 1024) {
        throw const FormatException('Select an MP4 video under 50 MB.');
      }
      final header = await file
          .openRead(0, 12)
          .fold<List<int>>(<int>[], (bytes, chunk) => bytes..addAll(chunk));
      if (header.length < 12 ||
          header[4] != 0x66 ||
          header[5] != 0x74 ||
          header[6] != 0x79 ||
          header[7] != 0x70) {
        throw const FormatException('The selected file is not an MP4 video.');
      }
      selected = file;
      selectedBytes = size;
      sentBytes = null;
      // A different file is a different reservation: never reuse its key.
      _uploadKey = null;
      _intent = null;
      if (draft != null) {
        // Replace the file of an existing draft after a failure.
        phase = UploadPhase.editing;
        status = null;
        _step = _Step.reserve;
      }
      _draftKey ??= _key();
    } on FormatException catch (failure) {
      error = failure.message;
    } catch (_) {
      error = 'The selected video could not be read.';
    } finally {
      _update();
    }
  }

  void clearSelection() {
    if (phase != UploadPhase.editing || draft != null) return;
    selected = null;
    selectedBytes = null;
    error = null;
    _update();
  }

  /// Starts the upload from the editing state (M-044 → M-046).
  Future<void> submit(String title, String description, String? category,
      String hashtags) async {
    if (phase != UploadPhase.editing || selected == null) return;
    detailsErrors =
        validateUploadDetails(title, description, category, hashtags);
    if (!detailsErrors.isEmpty) {
      error = null;
      _update();
      return;
    }
    if (!originalityAccepted) {
      error =
          'Confirm that you own this content or have permission to share it.';
      _update();
      return;
    }
    _details = UploadDetails(title.trim(), description, category!,
        normalizeTags(hashtags.split(RegExp(r'[\s,]+'))));
    _step = draft == null ? _Step.draft : _Step.reserve;
    await _run();
  }

  /// Resumes the interrupted step (M-047/M-048).
  Future<void> retry() async {
    if (phase != UploadPhase.interrupted && phase != UploadPhase.failed) return;
    if (phase == UploadPhase.failed) {
      final reason = status?.failureReason;
      if (reason == 'invalid_media' || selected == null) return;
      // Server-confirmed failure: replace the reservation with a fresh key.
      _uploadKey = null;
      _intent = null;
      _step = draft == null ? _Step.draft : _Step.reserve;
    }
    if (_details == null) return;
    await _run();
  }

  /// Re-submits completion for a transient preparation failure.
  Future<void> retryPreparation() async {
    final current = status;
    if (draft == null || current == null || !current.retryable) return;
    if (current.state != 'processing') return;
    _step = _Step.complete;
    await _run();
  }

  Future<void> _run() async {
    final generation = ++_generation;
    phase = UploadPhase.uploading;
    error = null;
    stalePreparation = false;
    _update();
    try {
      if (_step == _Step.draft) {
        final details = _details!;
        draft = await content.createDraft(
            title: details.title,
            description: details.description,
            category: details.category,
            tags: details.tags,
            idempotencyKey: _draftKey ??= _key());
        _step = _Step.reserve;
      }
      if (_step == _Step.reserve) {
        _uploadKey ??= _key();
        _intent = await content.reserveUpload(
            draft!, selectedBytes!, _uploadKey!,
            originalityAccepted: originalityAccepted);
        _step = _Step.transfer;
      }
      if (_step == _Step.transfer) {
        var intent = _intent;
        if (intent == null || intent.expiresAt.isBefore(DateTime.now())) {
          _uploadKey = _key();
          intent = _intent = await content.reserveUpload(
              draft!, selectedBytes!, _uploadKey!,
              originalityAccepted: originalityAccepted);
        }
        sentBytes = 0;
        _update();
        await content.uploadToProvider(
            intent, selected!.openRead(), selectedBytes!, onProgress: (sent) {
          if (_disposed || generation != _generation) return;
          final before = progress;
          sentBytes = sent;
          if (before == null || (progress! - before) >= 0.01) _update();
        });
        sentBytes = selectedBytes;
        _step = _Step.complete;
      }
      if (_step == _Step.complete) {
        status = await content.completeUpload(draft!.id);
        _settle();
        if (phase == UploadPhase.preparing) unawaited(_poll(generation));
      }
    } catch (failure) {
      if (_disposed || generation != _generation) return;
      final fallback = UploadPhase.interrupted;
      if (failure is ApiFailure &&
          _step == _Step.transfer &&
          failure.kind == FailureKind.expired) {
        // An expired storage grant is not a signed-out session.
        _uploadKey = null;
        _intent = null;
        _step = _Step.reserve;
        phase = fallback;
        error = 'The upload link expired. Try again.';
      } else if (failure is ApiFailure &&
          _step == _Step.draft &&
          failure.kind == FailureKind.invalid) {
        // The server rejected the story details: let the creator edit them.
        phase = UploadPhase.editing;
        error = failure.message;
      } else {
        _classify(failure, fallback: fallback);
        if (phase == UploadPhase.uploading) phase = fallback;
      }
      if (_step == _Step.transfer) sentBytes = null;
    } finally {
      _update();
    }
  }

  void _settle() {
    final current = status!;
    if (current.state == 'failed') {
      phase = UploadPhase.failed;
      error = null;
    } else if (current.state == 'draft') {
      // Completion did not move the video on; the owner may retry.
      phase = UploadPhase.interrupted;
      _step = _Step.reserve;
      _uploadKey = null;
      error = 'The service did not confirm receipt. Try again.';
    } else if (current.preparing) {
      phase = UploadPhase.preparing;
    } else {
      phase = UploadPhase.settled;
    }
  }

  Future<void> _poll(int generation) async {
    var failures = 0;
    for (var attempt = 0; attempt < maxPolls; attempt++) {
      final seconds = pollSchedule[min(attempt, pollSchedule.length - 1)];
      await _delay(Duration(seconds: seconds));
      if (_disposed || generation != _generation) return;
      try {
        status = await content.uploadStatus(draft!.id);
        failures = 0;
      } on ApiFailure catch (failure) {
        if (failure.kind == FailureKind.expired ||
            failure.kind == FailureKind.forbidden) {
          _classify(failure, fallback: UploadPhase.preparing);
          _update();
          return;
        }
        if (++failures >= 3) break;
        continue;
      } on FormatException {
        break;
      }
      _settle();
      _update();
      if (phase != UploadPhase.preparing) return;
    }
    if (_disposed || generation != _generation) return;
    stalePreparation = true;
    _update();
  }

  /// Manual refresh once automatic polling has stopped.
  Future<void> refreshStatus() async {
    final id = draft?.id;
    if (id == null || phase != UploadPhase.preparing) return;
    final generation = ++_generation;
    stalePreparation = false;
    error = null;
    _update();
    try {
      status = await content.uploadStatus(id);
      _settle();
      if (phase == UploadPhase.preparing) unawaited(_poll(generation));
    } on ApiFailure catch (failure) {
      _classify(failure, fallback: UploadPhase.preparing);
      stalePreparation = phase == UploadPhase.preparing;
    } on FormatException {
      stalePreparation = true;
      error = 'The video status could not be read.';
    } finally {
      _update();
    }
  }

  @override
  void dispose() {
    if (_disposed) return;
    _disposed = true;
    _generation++;
    selected = null;
    _draftKey = null;
    _uploadKey = null;
    _intent = null;
    super.dispose();
  }
}
