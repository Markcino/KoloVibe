import 'package:flutter/foundation.dart';
import '../../core/network/api_client.dart';
import 'live_content_repository.dart';

enum ManagePhase { loading, failed, ready }

/// M-053 Manage video: the creator's own video, publish, unpublish, edit and delete.
///
/// Moderation approval is never granted here: publishing only makes an approved video public, and the
/// server answers 409 `review_required` for anything else. Only one action runs at a time.
class ManageVideoController extends ChangeNotifier {
  ManageVideoController(this._repository, this.videoId);

  final LiveContentRepository _repository;
  final String videoId;

  ManagePhase phase = ManagePhase.loading;
  Object? loadError;
  OwnedVideo? video;
  bool busy = false;

  /// Shown above the actions after a failed or successful action; never raw service text.
  String? message;

  /// The session ended during an action: the screen offers sign-in and keeps the video on screen.
  bool sessionExpired = false;

  /// True once the video was deleted; the screen closes.
  bool deleted = false;
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
    phase = ManagePhase.loading;
    loadError = null;
    message = null;
    sessionExpired = false;
    _emit();
    try {
      video = await _repository.ownedVideo(videoId);
      phase = ManagePhase.ready;
    } on ApiFailure catch (failure) {
      loadError = failure;
      phase = ManagePhase.failed;
    } on FormatException {
      loadError = const ApiFailure(502, 'The video response was invalid.');
      phase = ManagePhase.failed;
    }
    _emit();
  }

  Future<bool> publish() => _run(
      () async =>
          video = await _repository.setVisibility(video!, publish: true),
      success: 'Your video is public.');

  Future<bool> unpublish() => _run(
      () async =>
          video = await _repository.setVisibility(video!, publish: false),
      success: 'Your video is no longer public.');

  Future<bool> edit(
          {String? title,
          String? description,
          String? category,
          List<String>? tags}) =>
      _run(
          () async => video = await _repository.editDetails(video!,
              title: title,
              description: description,
              category: category,
              tags: tags),
          success: 'Details saved.');

  Future<bool> delete() => _run(() async {
        await _repository.deleteVideo(video!);
        deleted = true;
      }, success: null);

  Future<bool> _run(Future<void> Function() action,
      {required String? success}) async {
    final current = video;
    if (busy || current == null) return false;
    busy = true;
    message = null;
    sessionExpired = false;
    _emit();
    try {
      await action();
      message = success;
      return true;
    } on ApiFailure catch (failure) {
      _fail(failure);
    } on FormatException {
      message = 'That change could not be completed.';
    } finally {
      busy = false;
      _emit();
    }
    return false;
  }

  void _fail(ApiFailure failure) {
    switch (failure.kind) {
      case FailureKind.offline:
        message = 'You are offline. Nothing was changed.';
      case FailureKind.expired:
        sessionExpired = true;
        message = 'Your session ended. Sign in to continue.';
      case FailureKind.forbidden:
        message = 'You cannot change this video.';
      case FailureKind.notFound:
        message = 'This video is no longer available.';
      case FailureKind.conflict:
        message = failure.code == 'review_required'
            ? 'This video must be approved before it can be public.'
            : 'This video changed. Refresh and try again.';
      case FailureKind.rateLimited:
        message = 'Too many attempts. Wait a moment, then try again.';
      case FailureKind.invalid:
        message = 'Check the details and try again.';
      case FailureKind.unavailable:
        message = 'The service is unavailable. Try again shortly.';
    }
  }
}

/// Plain-language state names; an unknown server state is shown as-is, never guessed.
String videoStateLabel(OwnedVideo video) => switch (video.state) {
      'draft' => 'Draft',
      'uploading' => 'Uploading',
      'processing' => 'Preparing your video',
      'failed' => 'Upload failed',
      'review' => 'Waiting for review',
      'published' => video.isPublic ? 'Public' : 'Approved, not public',
      'rejected' => 'Not approved',
      'removed' => 'Removed',
      _ => video.state,
    };
