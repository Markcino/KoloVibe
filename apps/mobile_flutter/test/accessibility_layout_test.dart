import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/app/app_dependencies.dart';
import 'package:kolovibe/app/kolovibe_app.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/demo/demo_repository.dart';

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
          dependencies: AppDependencies.preview(DemoRepository().services)));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pump(const Duration(milliseconds: 350));
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(seconds: 4));
    });
  }
}
