import '../core/presentation/feature_repository.dart';
import '../app/service_repositories.dart';

/// Local simulation only. This file is imported exclusively by main_demo.dart.
class DemoRepository extends UnavailableServices {
  ServiceRepositories get services => ServiceRepositories(
        account: this,
        discovery: this,
        creators: this,
        content: this,
        engagement: this,
        points: this,
        moderation: this,
        settings: this,
      );
  @override
  Future<UiResult> execute(UiRequest request) async {
    // Do not retain request fields, credentials, codes, or user content.
    await Future<void>.delayed(const Duration(milliseconds: 180));
    if ({
      UiOperation.share,
      UiOperation.deviceSettings,
      UiOperation.appStore,
    }.contains(request.operation)) {
      return const UiResult.unavailable();
    }
    return const UiResult.success(
      message: 'Demo simulation only — no live request was submitted.',
    );
  }
}
