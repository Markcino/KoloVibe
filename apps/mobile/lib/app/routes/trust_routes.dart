import 'package:flutter/widgets.dart';
import '../../features/moderation/live_moderation_repository.dart';
import '../../features/moderation/live_report_screen.dart';
import '../../features/points/live_points_screen.dart';
import 'route_context.dart';

/// Creator points, reports, appeals, notices, and account standing (M-061–M-078).
Widget? trustRoute(RouteContext context) {
  final deps = context.dependencies;
  final route = context.route;
  return switch (route.screen) {
    >= 61 && <= 69 when deps.livePoints != null => LivePointsScreen(
        route: route,
        catalog: context.catalog,
        repository: deps.livePoints!,
        videoTitle: deps.liveVideos == null
            ? null
            : (id) async => (await deps.liveVideos!.detail(id)).title),
    71 ||
    72 ||
    73 ||
    74 ||
    75
        when deps.liveAccount != null &&
            deps.liveVideos != null &&
            route.entityId != null =>
      LiveReportScreen(
          route: route,
          catalog: context.catalog,
          videos: deps.liveVideos!,
          moderation: LiveModerationRepository(deps.liveAccount!)),
    _ => null,
  };
}
