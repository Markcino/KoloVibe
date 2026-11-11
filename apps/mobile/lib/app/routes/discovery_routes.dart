import 'package:flutter/widgets.dart';
import '../../features/creators/live_creator_screen.dart';
import '../../features/discovery/live_video_screen.dart';
import '../../features/engagement/live_video_engagement_repository.dart';
import 'route_context.dart';

/// Home, explore, search, following, playback, and creator profiles (M-017–M-035).
Widget? discoveryRoute(RouteContext context) {
  final deps = context.dependencies;
  final route = context.route;
  return switch (route.screen) {
    17 || 18 || 19 || 24 when deps.liveVideos != null => LiveVideoScreen(
        route: route,
        catalog: context.catalog,
        repository: deps.liveVideos!,
        creators: deps.liveCreators,
        account: deps.liveAccount),
    25 when deps.liveVideos != null && route.entityId != null =>
      LiveVideoDetailScreen(
          id: route.entityId!,
          repository: deps.liveVideos!,
          engagement: deps.liveAccount == null
              ? null
              : LiveVideoEngagementRepository(deps.liveAccount!)),
    38 when deps.liveCreators != null && route.entityId != null =>
      LiveCreatorScreen(
          id: route.entityId!,
          repository: deps.liveCreators!,
          account: deps.liveAccount),
    _ => null,
  };
}
