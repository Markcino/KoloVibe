// The Business route range, the sixth bottom-bar tab and route dispatch.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/app/app_dependencies.dart';
import 'package:kolovibe/app/app_session.dart';
import 'package:kolovibe/app/routes/business_routes.dart';
import 'package:kolovibe/app/routes/route_context.dart';
import 'package:kolovibe/app/screen_route.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/features/business/business_pending_screen.dart';
import 'package:kolovibe/features/business/business_screens.dart';
import 'package:kolovibe/features/shell/main_shell.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late DesignCatalog catalog;
  setUpAll(() async => catalog = await DesignCatalog.load());

  Widget? build(int screen, AppDependencies dependencies) =>
      businessRoute(RouteContext(
          route: ScreenRoute(screen),
          catalog: catalog,
          dependencies: dependencies,
          session: AppSession()));

  test('the design catalog is untouched: still exactly 108 designed screens',
      () {
    expect(catalog.screens.length, 108);
  });

  test('Business owns exactly M-109 to M-144, and the route range accepts them',
      () {
    expect(BusinessScreens.first, 109);
    expect(BusinessScreens.last, 144);
    expect(const ScreenRoute(108).isBusiness, isFalse);
    expect(const ScreenRoute(145).valid, isFalse);
    expect(const ScreenRoute(0).valid, isFalse);
    for (var screen = 109; screen <= 144; screen++) {
      final route = ScreenRoute(screen);
      expect(route.valid && route.isBusiness, isTrue, reason: 'M-$screen');
      expect(route.name, '/mobile/M-$screen');
    }
  });

  test('the builder leaves every designed screen to the other domains', () {
    final live = AppDependencies.live('https://api.example.test/api/v1');
    for (var screen = 1; screen <= 108; screen++) {
      expect(build(screen, live), isNull, reason: 'M-$screen');
    }
  });

  test('every Business number gets a Business screen, never the design screen',
      () {
    final live = AppDependencies.live('https://api.example.test/api/v1');
    for (var screen = 109; screen <= 144; screen++) {
      expect(build(screen, live), isNotNull, reason: 'M-$screen');
      expect(build(screen, const AppDependencies.unavailable()), isNotNull,
          reason: 'M-$screen without a gateway');
    }
  });

  group('bottom navigation', () {
    late DesignNode navigation;
    // A Business screen has no recipe, so it borrows the Home navigation (as BusinessPage does).
    setUp(() => navigation = catalog[17].named('Primary navigation')!);

    Future<List<int>> pump(WidgetTester tester, int screen) async {
      final taps = <int>[];
      await tester.pumpWidget(MaterialApp(
          home: Scaffold(
              bottomNavigationBar: MainShell(
                  navigation: navigation,
                  screen: screen,
                  onSelected: taps.add))));
      await tester.pump();
      return taps;
    }

    bool selected(WidgetTester tester, String label) {
      final node = tester.getSemantics(
          find.ancestor(of: find.text(label), matching: find.byType(InkWell)));
      return node.flagsCollection.isSelected.name == 'isTrue';
    }

    testWidgets('has six tabs and the last one opens Businesses (M-109)',
        (tester) async {
      final taps = await pump(tester, 17);
      for (final label in [
        'Home',
        'Explore',
        'Create',
        'Videos',
        'Profile',
        'Businesses'
      ]) {
        expect(find.text(label), findsOneWidget, reason: label);
      }
      await tester.tap(find.text('Businesses'));
      expect(taps, [BusinessScreens.home]);
      await tester.tap(find.text('Home'));
      expect(taps.last, 17);
      expect(MainShell.targets.length, MainShell.labels.length);
    });

    testWidgets('a Business screen selects Businesses, not Home',
        (tester) async {
      for (final screen in [109, 113, 128, 144]) {
        await pump(tester, screen);
        expect(selected(tester, 'Businesses'), isTrue, reason: 'M-$screen');
        expect(selected(tester, 'Home'), isFalse, reason: 'M-$screen');
      }
    });

    testWidgets('creator screens still select their own tab', (tester) async {
      await pump(tester, 17);
      expect(selected(tester, 'Businesses'), isFalse);
      navigation = catalog[79].named('Primary navigation')!;
      await pump(tester, 79);
      expect(selected(tester, 'Profile'), isTrue);
      expect(selected(tester, 'Businesses'), isFalse);
    });
  });

  testWidgets('the placeholder says it is unavailable and offers no action',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
        home: BusinessPendingScreen(
            route: const ScreenRoute(109),
            catalog: catalog,
            available: false)));
    await tester.pump();
    expect(find.text('Businesses are unavailable'), findsOneWidget);
    expect(find.byType(TextButton), findsNothing);
    expect(find.byType(ElevatedButton), findsNothing);
  });
}
