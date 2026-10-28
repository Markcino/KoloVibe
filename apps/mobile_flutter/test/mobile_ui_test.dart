import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/app/app_dependencies.dart';
import 'package:kolovibe/app/kolovibe_app.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/core/presentation/feature_repository.dart';
import 'package:kolovibe/demo/demo_repository.dart';
import 'package:kolovibe/features/shell/screen_controller.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late DesignCatalog catalog;
  setUpAll(() async {
    catalog = await DesignCatalog.load();
    for (final font in ['Inter', 'PlusJakartaSans']) {
      final loader = FontLoader(font)
        ..addFont(rootBundle.load('assets/fonts/$font.ttf'));
      await loader.load();
    }
    final icons = FontLoader('MaterialIcons')
      ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
    await icons.load();
  });

  test(
    'Every design has an individual recipe, source node and local assets',
    () {
      expect(catalog.screens.keys.toSet(), {for (var i = 1; i <= 108; i++) i});
      for (final screen in catalog.screens.values) {
        expect(screen.figmaNode, isNotEmpty);
        for (final n in screen.root.descendants) {
          if (n.kind == 'image') {
            expect(n.asset, startsWith('assets/images/'));
            expect(File(n.asset!).lengthSync(), greaterThan(0));
          }
        }
      }
    },
  );

  test(
    'Unavailable services cannot claim success; sensitive fields are cleared',
    () async {
      final controller = ScreenController(const UnavailableRepository());
      controller.update('Password', 'transient-test-value');
      final result = await controller.submit(UiOperation.signIn);
      expect(result!.available, isFalse);
      expect(controller.fields.containsKey('Password'), isFalse);
      expect(controller.error, isNotNull);
      controller.dispose();
    },
  );

  for (var id = 1; id <= 108; id++) {
    testWidgets(
      'M-${id.toString().padLeft(3, '0')} renders and captures without layout errors',
      (tester) async {
        tester.view.physicalSize = const Size(390, 844);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final boundary = GlobalKey();
        await tester.pumpWidget(
          RepaintBoundary(
            key: boundary,
            child: KoloVibeApp(
              catalog: catalog,
              initialScreen: id,
              dependencies: AppDependencies.preview(DemoRepository().services),
            ),
          ),
        );
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 400));
        await tester.pump(const Duration(milliseconds: 400));
        // Images are decoded outside fake time before checking paint/layout.
        await tester.runAsync(() async {
          await Future<void>.delayed(const Duration(milliseconds: 60));
        });
        await tester.pump();
        expect(
          tester.takeException(),
          isNull,
          reason: 'M-$id must render without exceptions',
        );
        if (const bool.fromEnvironment('CAPTURE_UI')) {
          final render = boundary.currentContext!.findRenderObject()!
              as RenderRepaintBoundary;
          await tester.runAsync(() async {
            final image = await render.toImage(pixelRatio: 1);
            final bytes =
                await image.toByteData(format: ui.ImageByteFormat.png);
            final directory = Directory('build/ui-review')
              ..createSync(recursive: true);
            File(
              '${directory.path}/M-${id.toString().padLeft(3, '0')}.png',
            ).writeAsBytesSync(bytes!.buffer.asUint8List());
            image.dispose();
          });
        }
        await tester.pumpWidget(const SizedBox());
        await tester.pump(const Duration(seconds: 4));
      },
    );
  }

  testWidgets(
    'Normal entry has no demo controls and sign-in cannot fabricate a session',
    (tester) async {
      await tester.pumpWidget(KoloVibeApp(catalog: catalog, initialScreen: 4));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 400));
      expect(find.textContaining('DEMO ·'), findsNothing);
      await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
      await tester.pump();
      expect(find.textContaining('Enter email'), findsWidgets);
      expect(find.text('Good morning, Ama ☀'), findsNothing);
    },
  );

  testWidgets('Normal mode hides sample account and points data', (
    tester,
  ) async {
    await tester.pumpWidget(KoloVibeApp(catalog: catalog, initialScreen: 61));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.text('This service is not connected yet.'), findsOneWidget);
    expect(find.text('1,240'), findsNothing);
  });
}
