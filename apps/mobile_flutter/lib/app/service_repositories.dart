import '../core/presentation/feature_repository.dart';
import '../features/account/account_repository.dart';
import '../features/discovery/discovery_repository.dart';
import '../features/creators/creator_repository.dart';
import '../features/content/content_repository.dart';
import '../features/engagement/engagement_repository.dart';
import '../features/points/points_repository.dart';
import '../features/moderation/moderation_repository.dart';
import '../features/settings/settings_repository.dart';

/// The composition root is the only place that knows all service boundaries.
class ServiceRepositories {
  const ServiceRepositories({
    required this.account,
    required this.discovery,
    required this.creators,
    required this.content,
    required this.engagement,
    required this.points,
    required this.moderation,
    required this.settings,
  });
  const ServiceRepositories.unavailable()
      : account = const UnavailableServices(),
        discovery = const UnavailableServices(),
        creators = const UnavailableServices(),
        content = const UnavailableServices(),
        engagement = const UnavailableServices(),
        points = const UnavailableServices(),
        moderation = const UnavailableServices(),
        settings = const UnavailableServices();
  final AccountRepository account;
  final DiscoveryRepository discovery;
  final CreatorRepository creators;
  final ContentRepository content;
  final EngagementRepository engagement;
  final PointsRepository points;
  final ModerationRepository moderation;
  final SettingsRepository settings;

  FeatureRepository forOperation(UiOperation op) => switch (op) {
        UiOperation.like || UiOperation.follow => engagement,
        UiOperation.selectMedia ||
        UiOperation.upload ||
        UiOperation.unpublish ||
        UiOperation.deleteVideo =>
          content,
        UiOperation.report => moderation,
        UiOperation.privacyRequest || UiOperation.deviceSettings => settings,
        _ => account,
      };
}

class UnavailableServices extends UnavailableRepository
    implements
        AccountRepository,
        DiscoveryRepository,
        CreatorRepository,
        ContentRepository,
        EngagementRepository,
        PointsRepository,
        ModerationRepository,
        SettingsRepository {
  const UnavailableServices();
}

class RepositoryDispatcher implements FeatureRepository {
  const RepositoryDispatcher(this.services);
  final ServiceRepositories services;
  @override
  Future<UiResult> execute(UiRequest request) =>
      services.forOperation(request.operation).execute(request);
}
