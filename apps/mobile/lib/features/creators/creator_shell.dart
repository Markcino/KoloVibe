import 'package:flutter/material.dart';
import '../../app/screen_route.dart';
import '../../core/presentation/design_node.dart';
import '../shell/main_shell.dart';

/// Pushes [screen]; sign-in (M-004) returns to [returnTo] when given.
void openCreatorScreen(BuildContext context, int screen,
    {String? entityId, int? returnTo}) {
  final route = ScreenRoute(screen, entityId: entityId, returnTo: returnTo);
  Navigator.of(context).pushNamed(route.name, arguments: route);
}

/// Asks the user to sign in again, returning here afterwards.
void signInThenReturn(BuildContext context, int returnTo) =>
    openCreatorScreen(context, 4, returnTo: returnTo);

/// The designed primary navigation for [screen], or null when the recipe has none.
Widget? creatorNavigation(
    BuildContext context, DesignCatalog catalog, int screen) {
  final navigation = catalog[screen].named('Primary navigation');
  if (navigation == null) return null;
  return MainShell(
      navigation: navigation,
      screen: screen,
      onSelected: (target) {
        final route = ScreenRoute(target);
        Navigator.of(context)
            .pushReplacementNamed(route.name, arguments: route);
      });
}
