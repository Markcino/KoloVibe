import 'package:flutter/widgets.dart';
import '../../features/moderation/live_moderation_repository.dart';
import '../../features/moderation/live_notice_screen.dart';
import '../../features/moderation/live_appeal_screen.dart';
import '../../features/moderation/live_report_screen.dart';
import '../../features/moderation/live_standing_repository.dart';
import '../../features/moderation/live_standing_screen.dart';
import '../../features/points/live_points_screen.dart';
import '../../features/content/live_content_repository.dart';
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
    76 when deps.liveAccount != null && route.entityId != null =>
      LiveNoticeScreen(
          route: route,
          catalog: context.catalog,
          repository: LiveStandingRepository(deps.liveAccount!)),
    78 when deps.liveAccount != null && route.entityId != null =>
      LiveAppealScreen(
          route: route,
          catalog: context.catalog,
          standing: LiveStandingRepository(deps.liveAccount!),
          moderation: LiveModerationRepository(deps.liveAccount!)),
    77 when deps.liveAccount != null => LiveStandingScreen(
        catalog: context.catalog,
        repository: LiveStandingRepository(deps.liveAccount!),
        titleLookup: deps.liveContent == null
            ? null
            : (ids) => ownVideoTitles(deps.liveContent!, ids)),
    _ => null,
  };
}

/// Own-library titles for [ids], read page by page (bounded) and stopping
/// once every id is found. Missing ids are simply absent.
Future<Map<String, String>> ownVideoTitles(
    LiveContentRepository content, Set<String> ids) async {
  final found = <String, String>{};
  String? cursor;
  for (var page = 0; page < 5 && found.length < ids.length; page++) {
    final result = await content.library(cursor: cursor);
    for (final video in result.items) {
      if (ids.contains(video.id)) found[video.id] = video.title;
    }
    cursor = result.nextCursor;
    if (cursor == null) break;
  }
  return found;
}
