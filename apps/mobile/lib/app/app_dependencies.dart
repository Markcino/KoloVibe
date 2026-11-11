import '../core/presentation/feature_repository.dart';
import 'service_repositories.dart';
import '../core/network/api_client.dart';
import '../core/platform/device_bridge.dart';
import '../core/security/credential_store.dart';
import '../features/account/live_account_repository.dart';
import '../features/discovery/live_video_repository.dart';
import '../features/creators/live_creator_repository.dart';
import '../features/points/live_points_repository.dart';
import '../features/content/live_content_repository.dart';

class AppDependencies {
  const AppDependencies.unavailable()
      : services = const ServiceRepositories.unavailable(),
        liveAccount = null,
        liveVideos = null,
        liveCreators = null,
        livePoints = null,
        liveContent = null,
        api = null,
        device = const PlatformDeviceBridge();

  const AppDependencies._(
      this.services,
      this.liveAccount,
      this.liveVideos,
      this.liveCreators,
      this.livePoints,
      this.liveContent,
      this.api,
      this.device);

  factory AppDependencies.live(String baseUrl,
      {CredentialStore? credentialStore, DeviceBridge? device}) {
    final api = ApiClient(baseUrl);
    final account = LiveAccountRepository(
        api, credentialStore ?? const PlatformCredentialStore());
    return AppDependencies._(
      ServiceRepositories(
        account: account,
        discovery: const UnavailableServices(),
        creators: const UnavailableServices(),
        content: const UnavailableServices(),
        engagement: const UnavailableServices(),
        points: const UnavailableServices(),
        moderation: const UnavailableServices(),
        settings: const UnavailableServices(),
      ),
      account,
      LiveVideoRepository(api),
      LiveCreatorRepository(api),
      LivePointsRepository(account),
      LiveContentRepository(account),
      api,
      device ?? const PlatformDeviceBridge(),
    );
  }

  final ServiceRepositories services;
  final LiveAccountRepository? liveAccount;
  final LiveVideoRepository? liveVideos;
  final LiveCreatorRepository? liveCreators;
  final LivePointsRepository? livePoints;
  final LiveContentRepository? liveContent;

  /// Public gateway client for unauthenticated reads; null when unavailable.
  final ApiClient? api;
  final DeviceBridge device;
  FeatureRepository get repository => RepositoryDispatcher(services);
}
