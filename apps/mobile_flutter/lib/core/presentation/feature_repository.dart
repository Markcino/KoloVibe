/// UI integration boundaries. No endpoint or security policy is invented here.
enum UiOperation {
  signIn,
  register,
  verifyEmail,
  requestCode,
  requestReset,
  resetPassword,
  saveProfile,
  reauthenticate,
  signOut,
  selectMedia,
  upload,
  unpublish,
  deleteVideo,
  report,
  privacyRequest,
  deleteAccount,
  like,
  follow,
  share,
  deviceSettings,
  appStore,
}

class UiRequest {
  const UiRequest(this.operation, {this.fields = const {}});
  final UiOperation operation;

  /// Ephemeral form values. Repositories must not log or persist this map.
  final Map<String, String> fields;
}

class UiResult {
  const UiResult.success({this.message = 'Action completed.'})
      : available = true;
  const UiResult.unavailable()
      : available = false,
        message =
            'This service is not connected yet. No request was submitted.';
  final bool available;
  final String message;
}

abstract interface class FeatureRepository {
  Future<UiResult> execute(UiRequest request);
}

/// Secure default until the owning service and its ADRs are implemented.
class UnavailableRepository implements FeatureRepository {
  const UnavailableRepository();
  @override
  Future<UiResult> execute(UiRequest request) async =>
      const UiResult.unavailable();
}
