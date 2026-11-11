import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/app/app_dependencies.dart';
import 'package:kolovibe/app/kolovibe_app.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/core/theme/kolovibe_theme.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late DesignCatalog catalog;
  setUpAll(() async {
    catalog = await DesignCatalog.load();
    for (final family in ['Inter', 'PlusJakartaSans']) {
      await (FontLoader(family)
            ..addFont(rootBundle.load('assets/fonts/$family.ttf')))
          .load();
    }
  });
  testWidgets('Unavailable video state has accessible dark-background contrast',
      (tester) async {
    await tester.pumpWidget(KoloVibeApp(catalog: catalog, initialScreen: 24));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    double contrast(Color first, Color second) {
      final a = first.computeLuminance(), b = second.computeLuminance();
      return ((a > b ? a : b) + 0.05) / ((a > b ? b : a) + 0.05);
    }

    final title = tester.widget<Text>(
      find.text('This service is not connected yet.'),
    );
    final description = tester.widget<Text>(find.text(
      'Account access, content and actions become available when their secure services are connected.',
    ));
    for (final text in [title, description]) {
      expect(contrast(text.style!.color!, KoloVibeColors.deepNavy),
          greaterThanOrEqualTo(4.5));
    }
    final icon = tester.widget<Icon>(find.byIcon(Icons.cloud_off_outlined));
    expect(contrast(icon.color!, KoloVibeColors.deepNavy),
        greaterThanOrEqualTo(3));
    final button = tester.widget<FilledButton>(find.byType(FilledButton));
    final background = button.style!.backgroundColor!.resolve({});
    final foreground = button.style!.foregroundColor!.resolve({});
    expect(contrast(foreground!, background!), greaterThanOrEqualTo(4.5));
  });
  for (final id in [
    2,
    4,
    5,
    6,
    17,
    19,
    24,
    33,
    37,
    44,
    58,
    61,
    71,
    79,
    84,
    92,
    105,
    108
  ]) {
    testWidgets('M-$id fits a narrow device with enlarged text',
        (tester) async {
      tester.view.physicalSize = const Size(320, 568);
      tester.view.devicePixelRatio = 1;
      tester.platformDispatcher.textScaleFactorTestValue = 1.8;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      await tester.pumpWidget(KoloVibeApp(
          catalog: catalog,
          initialScreen: id,
          dependencies: const AppDependencies.unavailable()));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pump(const Duration(milliseconds: 350));
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(seconds: 4));
    });
  }
}
