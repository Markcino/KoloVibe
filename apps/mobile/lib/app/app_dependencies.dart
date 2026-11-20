import 'package:http/http.dart' as http;
import '../core/presentation/feature_repository.dart';
import 'service_repositories.dart';
import '../core/network/api_client.dart';
import '../core/platform/device_bridge.dart';
import '../core/security/credential_store.dart';
import '../features/account/live_account_repository.dart';
import '../features/discovery/live_video_repository.dart';
import '../features/discovery/search_history.dart';
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
        searchHistory = null,
        api = null,
        device = const PlatformDeviceBridge();

  const AppDependencies._(
      this.services,
      this.liveAccount,
      this.liveVideos,
      this.liveCreators,
      this.livePoints,
      this.liveContent,
      this.searchHistory,
      this.api,
      this.device);

  factory AppDependencies.live(String baseUrl,
      {CredentialStore? credentialStore,
      DeviceBridge? device,
      SearchHistoryStore? searchHistoryStore,
      http.Client? client}) {
    final api = ApiClient(baseUrl, client: client);
    final account = LiveAccountRepository(
        api, credentialStore ?? const PlatformCredentialStore());
    final history =
        SearchHistory(searchHistoryStore ?? const SecureSearchHistoryStore());
    account.onSessionEnded = history.clearAll;
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
      history,
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

  /// Device-local recent searches; never sent to the service.
  final SearchHistory? searchHistory;

  /// Public gateway client for unauthenticated reads; null when unavailable.
  final ApiClient? api;
  final DeviceBridge device;
  FeatureRepository get repository => RepositoryDispatcher(services);
}
