import 'package:flutter/foundation.dart';
import '../../core/network/api_client.dart';
import 'live_creator_repository.dart';
import 'live_own_creator_repository.dart';

enum OwnProfilePhase { loading, failed, ready }

/// Loads and edits the creator's own profile (M-038 / M-039).
///
/// [publicCreators] is optional: it supplies the published-video count, which
/// only the public creator read returns. A failure there never blocks the page.
class OwnProfileController extends ChangeNotifier {
  OwnProfileController(this._repository,
      {LiveCreatorRepository? publicCreators})
      : _publicCreators = publicCreators;

  final LiveOwnCreatorRepository _repository;
  final LiveCreatorRepository? _publicCreators;

  OwnProfilePhase phase = OwnProfilePhase.loading;
  Object? error;
  OwnCreator? profile;
  int? publishedVideoCount;

  /// Set when [save] fails; [handleError] is the field-level handle problem.
  String? saveError;
  String? handleError;
  bool saving = false;
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
    phase = OwnProfilePhase.loading;
    error = null;
    _emit();
    try {
      final own = await _repository.profile();
      if (_disposed) return;
      profile = own;
      phase = OwnProfilePhase.ready;
      _emit();
      await _loadCount(own.id);
      return;
    } on ApiFailure catch (failure) {
      error = failure;
      phase = OwnProfilePhase.failed;
    } on FormatException {
      error = const ApiFailure(
          503, 'Your creator profile could not be read. Try again.');
      phase = OwnProfilePhase.failed;
    }
    _emit();
  }

  Future<void> _loadCount(String creatorId) async {
    final publicCreators = _publicCreators;
    if (publicCreators == null) return;
    try {
      final count =
          (await publicCreators.detail(creatorId)).publishedVideoCount;
      if (_disposed) return;
      publishedVideoCount = count;
      _emit();
    } on ApiFailure {
      // The count is a convenience; the profile itself is still correct.
    } on FormatException {
      // Ignore an invalid public read for the same reason.
    }
  }

  /// A problem with the handle the user typed, or null.
  static String? handleProblem(String handle) =>
      creatorHandleProblem(handle.trim());

  /// Returns true when the profile was saved.
  Future<bool> save(
      {required String displayName,
      required String bio,
      required String location,
      required String handle}) async {
    final current = profile;
    if (saving || current == null) return false;
    saveError = null;
    handleError = null;
    final problem =
        handle.trim() == current.handle ? null : handleProblem(handle);
    if (problem != null) {
      handleError = problem;
      _emit();
      return false;
    }
    saving = true;
    _emit();
    try {
      profile = await _repository.update(current,
          displayName: displayName,
          bio: bio,
          location: location,
          handle: handle);
      saving = false;
      _emit();
      return true;
    } on ApiFailure catch (failure) {
      if (failure.status == 409 && failure.code == 'handle_taken') {
        handleError = 'That handle is already taken. Choose another.';
      } else if (failure.kind == FailureKind.expired ||
          failure.kind == FailureKind.offline) {
        error = failure;
        saveError = failure.kind == FailureKind.offline
            ? 'You are offline. Your changes are still here; try again when connected.'
            : 'Your session expired. Sign in again to save.';
      } else {
        saveError = failure.message;
      }
    } on FormatException catch (failure) {
      saveError = failure.message == 'Nothing to save'
          ? 'There are no changes to save.'
          : 'Check your details, then try again.';
    }
    saving = false;
    _emit();
    return false;
  }
}
