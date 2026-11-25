import 'package:flutter/material.dart';

import '../../app/screen_route.dart';
import '../../core/presentation/design_node.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../shell/main_shell.dart';

/// The shared frame of every Business screen: a titled app bar with a back button, the app's primary navigation
/// (Businesses tab selected), and a safe scrolling body. Business screens are implementation-led from the design
/// system, not from designed frames (owner decision A1), so they share this one frame instead of a design recipe.
class BusinessPage extends StatelessWidget {
  const BusinessPage({
    super.key,
    required this.screen,
    required this.catalog,
    required this.title,
    required this.child,
    this.actions = const [],
    this.scroll = true,
    this.showNavigation = true,
  });

  final int screen;
  final DesignCatalog catalog;
  final String title;
  final Widget child;
  final List<Widget> actions;

  /// False when [child] manages its own scrolling (lists).
  final bool scroll;
  final bool showNavigation;

  @override
  Widget build(BuildContext context) {
    final body = scroll
        ? SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
            child: child,
          )
        : child;
    return Scaffold(
      appBar: AppBar(
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        automaticallyImplyLeading: false,
        leading: Navigator.of(context).canPop()
            ? IconButton(
                tooltip: 'Back',
                icon: const Icon(Icons.arrow_back),
                onPressed: () => Navigator.of(context).maybePop(),
              )
            : null,
        title: Semantics(
          header: true,
          child: Text(title, style: KoloVibeText.heading(20)),
        ),
        actions: actions,
      ),
      body: SafeArea(top: false, bottom: false, child: body),
      bottomNavigationBar: showNavigation ? _navigation(context) : null,
    );
  }

  /// The designed primary navigation, taken from Home (M-017), since a Business screen has no design recipe of its own.
  Widget? _navigation(BuildContext context) {
    final navigation = catalog[17].named('Primary navigation');
    if (navigation == null) return null;
    return MainShell(
      navigation: navigation,
      screen: screen,
      onSelected: (target) {
        final route = ScreenRoute(target);
        Navigator.of(context)
            .pushReplacementNamed(route.name, arguments: route);
      },
    );
  }
}

/// Pushes a Business screen. [entityId] carries the business, inquiry or review the screen is about.
void openBusiness(BuildContext context, int screen,
    {String? entityId, int? returnTo}) {
  final route = ScreenRoute(screen, entityId: entityId, returnTo: returnTo);
  Navigator.of(context).pushNamed(route.name, arguments: route);
}

/// Opens the one sign-in screen (M-004). After signing in the person returns to [returnTo].
void signInForBusiness(BuildContext context, int returnTo) =>
    openBusiness(context, 4, returnTo: returnTo);

/// Replaces the current screen, so back does not return to a finished form.
void replaceBusiness(BuildContext context, int screen, {String? entityId}) {
  final route = ScreenRoute(screen, entityId: entityId);
  Navigator.of(context).pushReplacementNamed(route.name, arguments: route);
}
