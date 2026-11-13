// Route dispatch only; the screens use fake repositories elsewhere.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/app/app_dependencies.dart';
import 'package:kolovibe/app/app_session.dart';
import 'package:kolovibe/app/routes/creator_routes.dart';
import 'package:kolovibe/app/routes/route_context.dart';
import 'package:kolovibe/app/screen_route.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/features/content/live_content_screen.dart';
import 'package:kolovibe/features/content/live_create_original_screen.dart';
import 'package:kolovibe/features/creators/live_become_creator_screen.dart';
import 'package:kolovibe/features/creators/live_creator_studio_screen.dart';
import 'package:kolovibe/features/creators/live_edit_creator_profile_screen.dart';
import 'package:kolovibe/features/creators/live_own_profile_screen.dart';

void main() {
  late DesignCatalog catalog;
  setUpAll(() async => catalog = await DesignCatalog.load());

  Widget? build(int screen, AppDependencies dependencies) =>
      creatorRoute(RouteContext(
          route: ScreenRoute(screen),
          catalog: catalog,
          dependencies: dependencies,
          session: AppSession()));

  test('without a configured gateway no creator screen is live', () {
    for (final screen in [36, 37, 38, 39, 40, 41, 42, 43, 44]) {
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

  testWidgets('with a gateway M-036 to M-040 open the live creator screens',
      (tester) async {
    final live = AppDependencies.live('https://api.example.test/api/v1');
    expect(build(36, live), isA<LiveBecomeCreatorScreen>());
    expect(build(37, live), isA<LiveCreatorStudioScreen>());
    expect(build(38, live), isA<LiveOwnProfileScreen>());
    expect(build(39, live), isA<LiveEditCreatorProfileScreen>());
    expect(build(40, live), isA<LiveContentScreen>());
  });

  testWidgets('screens without a live contract stay protected fallbacks',
      (tester) async {
    // M-045: no frame API. M-050-M-057: outcomes and management, M-058-M-060:
    // analytics. Each is a later journey; none may show design sample data.
    final live = AppDependencies.live('https://api.example.test/api/v1');
    for (final screen in [45, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60]) {
      expect(build(screen, live), isNull, reason: 'M-0$screen');
    }
  });
}
