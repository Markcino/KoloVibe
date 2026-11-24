import 'package:flutter/widgets.dart';

import '../../features/business/business_pending_screen.dart';
import 'route_context.dart';

/// Business discovery, customer, owner and staff screens (M-109–M-144). These are native screens built from the design
/// system (owner decision A1); they are not part of the 108-screen design catalog.
Widget? businessRoute(RouteContext context) {
  final route = context.route;
  if (!route.isBusiness) return null;
  // Business numbers have no design recipe, so the generic design screen must never see them.
  final repository = context.dependencies.liveBusiness;
  if (repository == null) {
    return BusinessPendingScreen(
        route: route, catalog: context.catalog, available: false);
  }
  return switch (route.screen) {
    _ => BusinessPendingScreen(route: route, catalog: context.catalog),
  };
}
