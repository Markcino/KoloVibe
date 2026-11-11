import 'package:flutter/material.dart';
import '../../features/creators/live_creator_screen.dart';
import '../../features/discovery/live_video_screen.dart';
import '../../features/discovery/discovery_catalog_screen.dart';
import '../../features/discovery/vertical_video_feed.dart';
import '../../features/engagement/live_video_engagement_repository.dart';
import 'route_context.dart';

/// Home, explore, search, following, playback, and creator profiles (M-017–M-035).
Widget? discoveryRoute(RouteContext context) {
  final deps = context.dependencies;
  final route = context.route;
  if (deps.liveVideos != null &&
      route.entityId == null &&
      {25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35}.contains(route.screen)) {
    return Scaffold(
        appBar: AppBar(title: const Text('Explore originals')),
        body: const Center(
            child:
                Text('Choose a video or creator from Explore to continue.')));
  }
  return switch (route.screen) {
    17 ||
    18 ||
    19 ||
    20 ||
    21 ||
    22 ||
    23 ||
    27 when deps.liveVideos != null =>
      DiscoveryCatalogScreen(
          screen: route.screen,
          repository: deps.liveVideos!,
          catalog: context.catalog,
          creators: deps.liveCreators,
          account: deps.liveAccount,
          creatorId: route.entityId),
    24 when deps.liveVideos != null => VerticalVideoFeed(
        repository: deps.liveVideos!,
        device: deps.device,
        engagement: deps.liveAccount == null
            ? null
            : LiveVideoEngagementRepository(deps.liveAccount!)),
    25 ||
    29 ||
    30 ||
    31 ||
    32 ||
    33 ||
    34 ||
    35 when deps.liveVideos != null && route.entityId != null =>
      LiveVideoDetailScreen(
          id: route.entityId!,
          device: deps.device,
          repository: deps.liveVideos!,
          engagement: deps.liveAccount == null
              ? null
              : LiveVideoEngagementRepository(deps.liveAccount!)),
    26 ||
    28 when deps.liveCreators != null && route.entityId != null =>
      LiveCreatorScreen(
          id: route.entityId!,
          repository: deps.liveCreators!,
          account: deps.liveAccount),
    _ => null,
  };
}
