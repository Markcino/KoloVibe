// Route dispatch only; the screens use fake repositories elsewhere.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/app/app_dependencies.dart';
import 'package:kolovibe/app/app_session.dart';
import 'package:kolovibe/app/routes/route_context.dart';
import 'package:kolovibe/app/routes/trust_routes.dart';
import 'package:kolovibe/app/screen_route.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/features/moderation/live_appeal_screen.dart';
import 'package:kolovibe/features/moderation/live_notice_screen.dart';
import 'package:kolovibe/features/moderation/live_report_screen.dart';
import 'package:kolovibe/features/moderation/live_standing_screen.dart';
import 'package:kolovibe/features/points/live_points_screen.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late DesignCatalog catalog;
  setUpAll(() async => catalog = await DesignCatalog.load());

  Widget? build(int screen, AppDependencies dependencies, {String? entityId}) =>
      trustRoute(RouteContext(
          route: ScreenRoute(screen, entityId: entityId),
          catalog: catalog,
          dependencies: dependencies,
          session: AppSession()));

  test('without a configured gateway no trust screen is live', () {
    for (var screen = 61; screen <= 78; screen++) {
      expect(build(screen, const AppDependencies.unavailable()), isNull,
          reason: 'M-0$screen');
    }
  });

  test('with a gateway M-061 to M-069 open the live points screens', () {
    final live = AppDependencies.live('https://api.example.test/api/v1');
    for (var screen = 61; screen <= 69; screen++) {
      expect(build(screen, live), isA<LivePointsScreen>(),
          reason: 'M-0$screen');
    }
  });

  test('reporting screens still need a video; others stay protected', () {
    final live = AppDependencies.live('https://api.example.test/api/v1');
    expect(build(71, live), isNull);
    expect(build(71, live, entityId: '00000000-0000-4000-8000-000000000003'),
        isA<LiveReportScreen>());
    // M-070 is the player's own control; M-078 needs a video.
    for (final screen in [70, 78]) {
      expect(build(screen, live), isNull, reason: 'M-0$screen');
    }
  });

  test('M-078 opens the live appeal screen for a video', () {
    final live = AppDependencies.live('https://api.example.test/api/v1');
    expect(build(78, live, entityId: '00000000-0000-4000-8000-000000000003'),
        isA<LiveAppealScreen>());
    expect(
        build(78, const AppDependencies.unavailable(),
            entityId: '00000000-0000-4000-8000-000000000003'),
        isNull);
  });

  test('M-076 needs a video; M-077 needs only a signed-in gateway', () {
    final live = AppDependencies.live('https://api.example.test/api/v1');
    expect(build(76, live), isNull);
    expect(build(76, live, entityId: '00000000-0000-4000-8000-000000000003'),
        isA<LiveNoticeScreen>());
    expect(build(77, live), isA<LiveStandingScreen>());
    expect(build(77, const AppDependencies.unavailable()), isNull);
  });
}
