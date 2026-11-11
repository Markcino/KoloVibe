import 'package:flutter/widgets.dart';
import '../../features/account/account_sessions_screen.dart';
import '../../features/account/live_account_screen.dart';
import '../../features/settings/live_settings_repository.dart';
import '../../features/settings/live_settings_screen.dart';
import 'route_context.dart';

/// Profile, settings, security, privacy, help, legal, and system states (M-079–M-108).
Widget? settingsRoute(RouteContext context) {
  final deps = context.dependencies;
  final route = context.route;
  final account = deps.liveAccount;
  if (account == null) return null;
  return switch (route.screen) {
    83 => AccountSessionsScreen(repository: account),
    84 || 85 || 86 || 91 || 92 || 93 || 94 => LiveSettingsScreen(
        route: route,
        catalog: context.catalog,
        repository: LiveSettingsRepository(account),
        account: account),
    79 => LiveAccountScreen(repository: account, catalog: context.catalog),
    _ => null,
  };
}
