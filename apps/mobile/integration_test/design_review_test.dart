import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:kolovibe/app/app_dependencies.dart';
import 'package:kolovibe/app/kolovibe_app.dart';
import 'package:kolovibe/core/presentation/design_node.dart';

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  late DesignCatalog catalog;

  setUpAll(() async => catalog = await DesignCatalog.load());

  testWidgets('Capture all 108 current routes on the device', (tester) async {
    final coverage = <String>['screen,state,figma_node'];
    for (var id = 1; id <= 108; id++) {
      final name = 'M-${id.toString().padLeft(3, '0')}';
      await tester.pumpWidget(KoloVibeApp(
        key: ValueKey(name),
        catalog: catalog,
        initialScreen: id,
        dependencies: const AppDependencies.unavailable(),
      ));
      await tester.pump();
      final context = tester.element(find.byType(Scaffold).first);
      await tester.runAsync(() async {
        await precacheImage(
            const AssetImage('assets/images/logo.png'), context);
        for (final node in catalog[id].root.descendants) {
          final asset = node.asset;
          if (node.kind != 'image' || asset == null) continue;
          if (asset.endsWith('.svg')) {
            final loader = SvgAssetLoader(asset);
            await svg.cache.putIfAbsent(
              loader.cacheKey(context),
              () => loader.loadBytes(context),
            );
          } else {
            await precacheImage(AssetImage(asset), context);
          }
        }
      });
      await tester.pump(const Duration(milliseconds: 400));
      expect(tester.takeException(), isNull, reason: '$name layout');
      final state =
          find.text('This service is not connected yet.').evaluate().isEmpty
              ? 'presentation'
              : 'unavailable';
      coverage.add('$name,$state,${catalog[id].figmaNode}');
      await binding.takeScreenshot(name);
      await tester.pumpWidget(const SizedBox());
      await tester.pump();
    }
    binding.reportData ??= {};
    binding.reportData!['coverage'] = '${coverage.join('\n')}\n';
  });

  testWidgets('Welcome navigates to sign-in and validates an empty form',
      (tester) async {
    await tester.pumpWidget(KoloVibeApp(catalog: catalog, initialScreen: 2));
    await tester.pumpAndSettle();
    final signIn = find.widgetWithText(FilledButton, 'Sign in');
    await tester.ensureVisible(signIn);
    await tester.tap(signIn);
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Enter email'), findsWidgets);
    expect(tester.takeException(), isNull);
    await binding.takeScreenshot('sign-in-validation');
  });

  const gateway = String.fromEnvironment('KOLOVIBE_API_URL');
  if (gateway.isNotEmpty) {
    testWidgets(
        'Configured public discovery routes load without a test account',
        (tester) async {
      for (final id in [17, 19, 24]) {
        await tester.pumpWidget(KoloVibeApp(
          key: ValueKey('live-$id'),
          catalog: catalog,
          initialScreen: id,
          dependencies: AppDependencies.live(gateway),
        ));
        await tester.pumpAndSettle(const Duration(milliseconds: 200));
        expect(find.byType(CircularProgressIndicator), findsNothing);
        expect(find.text('No originals are available yet.'), findsOneWidget);
        expect(tester.takeException(), isNull);
        await binding.takeScreenshot('live-M-${id.toString().padLeft(3, '0')}');
        await tester.pumpWidget(const SizedBox());
        await tester.pump();
      }
    });
  }
}
