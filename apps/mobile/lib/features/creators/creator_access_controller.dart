import 'package:flutter/foundation.dart';
import '../../core/network/api_client.dart';
import 'live_creator_onboarding_repository.dart';
import 'live_own_creator_repository.dart';

/// Where the signed-in account stands in creator onboarding (M-036 / M-037).
enum CreatorAccessPhase {
  loading,

  /// The status could not be read; see [CreatorAccessController.error].
  failed,

  /// No invitation exists for this account. Invitations are issued by staff.
  noInvitation,
  invited,
  pending,
  rejected,

  /// Approved, but the server reports uploads as not currently allowed.
  restricted,
  eligible,
}

/// Reads real application and eligibility state, and submits the application.
class CreatorAccessController extends ChangeNotifier {
  CreatorAccessController(this._repository);

  final LiveCreatorOnboardingRepository _repository;

  CreatorAccessPhase phase = CreatorAccessPhase.loading;

  /// The failure behind [CreatorAccessPhase.failed] (offline, expired, ...).
  Object? error;

  /// A problem with the last application attempt, shown beside the form.
  String? submitError;
  bool submitting = false;
  UploadEligibility? eligibility;
  CreatorApplication? application;
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
    phase = CreatorAccessPhase.loading;
    error = null;
    _emit();
    try {
      final eligibility = await _repository.eligibility();
      final application = await _repository.application();
      if (_disposed) return;
      this.eligibility = eligibility;
      this.application = application;
      phase = eligibility.eligible
          ? CreatorAccessPhase.eligible
          : switch (application?.status) {
              'invited' => CreatorAccessPhase.invited,
              'pending' => CreatorAccessPhase.pending,
              'rejected' => CreatorAccessPhase.rejected,
              'approved' => CreatorAccessPhase.restricted,
              _ => CreatorAccessPhase.noInvitation,
            };
    } on ApiFailure catch (failure) {
      error = failure;
      phase = CreatorAccessPhase.failed;
    } on FormatException {
      error =
          const ApiFailure(503, 'Creator status could not be read. Try again.');
      phase = CreatorAccessPhase.failed;
    }
    _emit();
  }

  /// A problem the user can fix before anything is sent, else null.
  static String? handleProblem(String handle) =>
      creatorHandleProblem(handle.trim());

  Future<void> submit(
      {required String handle,
      required bool adultAttested,
      required bool rightsAttested}) async {
    if (submitting || phase != CreatorAccessPhase.invited) return;
    final problem = handleProblem(handle);
    if (problem != null) {
      submitError = problem;
      _emit();
      return;
    }
    if (!adultAttested || !rightsAttested) {
      submitError = 'Confirm both statements to continue.';
      _emit();
      return;
    }
    submitting = true;
    submitError = null;
    _emit();
    try {
      await _repository.submit(
          handle: handle,
          adultAttested: adultAttested,
          rightsAttested: rightsAttested);
      submitting = false;
      await load();
      return;
    } on ApiFailure catch (failure) {
      if (failure.kind == FailureKind.expired ||
          failure.kind == FailureKind.offline) {
        error = failure;
        phase = CreatorAccessPhase.failed;
      } else {
        submitError = failure.kind == FailureKind.conflict
            ? 'That handle or application can’t be used. Choose another handle.'
            : failure.message;
      }
    } on FormatException {
      submitError = 'Check your handle and statements, then try again.';
    }
    submitting = false;
    _emit();
  }
}
