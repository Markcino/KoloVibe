import 'package:flutter/foundation.dart';
import '../../core/network/api_client.dart';
import 'live_video_engagement_repository.dart';

class LiveVideoEngagementController extends ChangeNotifier {
  LiveVideoEngagementController(this.repository, this.videoId);

  final LiveVideoEngagementRepository repository;
  final String videoId;
  bool? liked;
  bool likeBusy = false;
  String? likeError;
  bool playbackBusy = false;
  String? playbackError;
  PlaybackGrant? grant;
  bool _progressBusy = false;
  int _reportedPosition = 0;
  bool _disposed = false;

  void _update() {
    if (!_disposed) notifyListeners();
  }

  Future<void> loadLike() async {
    likeError = null;
    likeBusy = true;
    _update();
    try {
      liked = await repository.likeState(videoId);
    } on ApiFailure catch (failure) {
      likeError = failure.status == 401
          ? 'Sign in to like this original.'
          : failure.message;
    } on FormatException {
      likeError = 'The like state could not be read.';
    } finally {
      likeBusy = false;
      _update();
    }
  }

  Future<void> toggleLike() async {
    if (likeBusy || liked == null) return;
    likeBusy = true;
    likeError = null;
    _update();
    try {
      liked = await repository.setLiked(videoId, !liked!);
    } on ApiFailure catch (failure) {
      likeError = failure.status == 401
          ? 'Your session expired. Sign in again.'
          : failure.message;
    } on FormatException {
      likeError = 'The like change could not be confirmed.';
    } finally {
      likeBusy = false;
      _update();
    }
  }

  Future<PlaybackGrant?> startPlayback() async {
    if (playbackBusy) return null;
    playbackBusy = true;
    playbackError = null;
    _update();
    try {
      grant = await repository.startPlayback(videoId);
      _reportedPosition = 0;
      return grant;
    } on ApiFailure catch (failure) {
      playbackError = failure.status == 401
          ? 'Sign in to watch this original.'
          : failure.message;
      return null;
    } on FormatException {
      playbackError = 'The playback grant was invalid.';
      return null;
    } finally {
      playbackBusy = false;
      _update();
    }
  }

  Future<void> reportProgress(Duration position,
      {bool completed = false}) async {
    final session = grant?.sessionId;
    final milliseconds = position.inMilliseconds;
    if (_progressBusy ||
        session == null ||
        milliseconds <= _reportedPosition ||
        milliseconds > 300000 ||
        !completed && milliseconds - _reportedPosition < 3000) {
      return;
    }
    _progressBusy = true;
    try {
      await repository.reportProgress(videoId, session, milliseconds);
      _reportedPosition = milliseconds;
    } on ApiFailure catch (failure) {
      // A stale or revoked session must not keep reporting progress.
      if (failure.status == 401 ||
          failure.status == 403 ||
          failure.status == 409) {
        grant = null;
        _update();
      }
    } on FormatException {
      grant = null;
      _update();
    } finally {
      _progressBusy = false;
    }
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
