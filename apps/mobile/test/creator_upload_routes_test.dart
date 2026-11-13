// Route dispatch only; the screens use fake repositories elsewhere.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/app/app_dependencies.dart';
import 'package:kolovibe/app/app_session.dart';
import 'package:kolovibe/app/routes/creator_routes.dart';
import 'package:kolovibe/app/routes/route_context.dart';
import 'package:kolovibe/app/screen_route.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/features/content/live_create_original_screen.dart';

void main() {
  late DesignCatalog catalog;
  setUpAll(() async => catalog = await DesignCatalog.load());

  Widget? build(int screen, AppDependencies dependencies) =>
      creatorRoute(RouteContext(
          route: ScreenRoute(screen),
          catalog: catalog,
          dependencies: dependencies,
          session: AppSession()));

  test('without a configured gateway no upload step is live', () {
    for (final screen in [41, 42, 43, 44]) {
      expect(build(screen, const AppDependencies.unavailable()), isNull);
    }
  });

  testWidgets('with a gateway M-041 to M-044 open the live upload flow',
      (tester) async {
    final live = AppDependencies.live('https://api.example.test/api/v1');
    for (final screen in [41, 42, 43, 44]) {
      expect(build(screen, live), isA<LiveCreateOriginalScreen>(),
          reason: 'M-0$screen');
    }
    // M-045 (cover) and the progress/outcome recipes stay protected fallbacks:
    // they have no meaningful cold entry and M-045 has no frame-picker API.
    for (final screen in [45, 46, 47, 48, 49]) {
      expect(build(screen, live), isNull, reason: 'M-0$screen');
    }
  });
}
