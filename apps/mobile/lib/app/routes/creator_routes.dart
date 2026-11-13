import 'package:flutter/widgets.dart';
import '../../features/content/live_content_screen.dart';
import '../../features/content/live_create_original_screen.dart';
import '../../features/creators/live_become_creator_screen.dart';
import '../../features/creators/live_creator_onboarding_repository.dart';
import '../../features/creators/live_creator_studio_screen.dart';
import '../../features/creators/live_edit_creator_profile_screen.dart';
import '../../features/creators/live_own_creator_repository.dart';
import '../../features/creators/live_own_profile_screen.dart';
import 'route_context.dart';

/// Creator studio: onboarding, profile, library, upload, publishing, analytics (M-036–M-060).
Widget? creatorRoute(RouteContext context) {
  final deps = context.dependencies;
  final route = context.route;
  final account = deps.liveAccount;
  return switch (route.screen) {
    // Onboarding, studio home and own profile: all read the signed-in
    // account's real state through the gateway.
    36 when account != null => LiveBecomeCreatorScreen(
        catalog: context.catalog,
        onboarding: LiveCreatorOnboardingRepository(account)),
    37 when account != null => LiveCreatorStudioScreen(
        catalog: context.catalog,
        onboarding: LiveCreatorOnboardingRepository(account),
        profiles: LiveOwnCreatorRepository(account)),
    38 when account != null => LiveOwnProfileScreen(
        catalog: context.catalog,
        profiles: LiveOwnCreatorRepository(account),
        publicCreators: deps.liveCreators),
    39 when account != null => LiveEditCreatorProfileScreen(
        catalog: context.catalog, profiles: LiveOwnCreatorRepository(account)),
    40 when deps.liveContent != null => LiveContentScreen(
        route: route, catalog: context.catalog, repository: deps.liveContent!),
    // M-041 is the entry; M-042–M-044 are its file, check and story steps.
    41 ||
    42 ||
    43 ||
    44 when deps.liveContent != null && account != null =>
      LiveCreateOriginalScreen(
          content: deps.liveContent!,
          onboarding: LiveCreatorOnboardingRepository(account)),
    _ => null,
  };
}
