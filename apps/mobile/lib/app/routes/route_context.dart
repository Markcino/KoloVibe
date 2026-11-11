import 'package:flutter/widgets.dart';
import '../../core/presentation/design_node.dart';
import '../app_dependencies.dart';
import '../app_session.dart';
import '../screen_route.dart';

/// Everything a domain route builder may use to construct a live screen.
class RouteContext {
  const RouteContext({
    required this.route,
    required this.catalog,
    required this.dependencies,
    required this.session,
  });

  final ScreenRoute route;
  final DesignCatalog catalog;
  final AppDependencies dependencies;
  final AppSession session;
}

/// Returns a live screen for routes the domain owns, or null to fall through.
typedef DomainRouteBuilder = Widget? Function(RouteContext context);
