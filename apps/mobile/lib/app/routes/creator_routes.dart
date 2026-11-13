import 'package:flutter/widgets.dart';
import '../../features/content/live_content_screen.dart';
import '../../features/content/live_create_original_screen.dart';
import '../../features/creators/live_creator_onboarding_repository.dart';
import 'route_context.dart';

/// Creator studio: onboarding, profile, library, upload, publishing, analytics (M-036–M-060).
Widget? creatorRoute(RouteContext context) {
  final deps = context.dependencies;
  final route = context.route;
  return switch (route.screen) {
    37 || 40 when deps.liveContent != null => LiveContentScreen(
        route: route,
        catalog: context.catalog,
        repository: deps.liveContent!,
        onboarding: route.screen == 37 && deps.liveAccount != null
            ? LiveCreatorOnboardingRepository(deps.liveAccount!)
            : null),
    // M-041 is the entry; M-042–M-044 are its file, check and story steps.
    41 ||
    42 ||
    43 ||
    44 when deps.liveContent != null && deps.liveAccount != null =>
      LiveCreateOriginalScreen(
          content: deps.liveContent!,
          onboarding: LiveCreatorOnboardingRepository(deps.liveAccount!)),
    _ => null,
  };
}
