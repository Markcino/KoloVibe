import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

/// iPhone viewports used for the design audit. Insets mirror the real device
/// status bar and home indicator.
class AuditViewport {
  const AuditViewport(this.name, this.size, this.top, this.bottom);
  final String name;
  final Size size;
  final double top, bottom;

  /// iPhone 14/15/16: 390 × 844, notch and home indicator.
  static const standard = AuditViewport('390x844', Size(390, 844), 47, 34);

  /// iPhone SE (3rd generation): 375 × 667, no notch, no home indicator.
  static const small = AuditViewport('375x667', Size(375, 667), 20, 0);
}

bool _fontsLoaded = false;

/// Registers the bundled brand fonts so renders use Inter and Plus Jakarta Sans.
Future<void> loadBrandFonts() async {
  if (_fontsLoaded) return;
  for (final entry in {
    'Inter': 'assets/fonts/Inter.ttf',
    'PlusJakartaSans': 'assets/fonts/PlusJakartaSans.ttf',
  }.entries) {
    final loader = FontLoader(entry.key)..addFont(rootBundle.load(entry.value));
    await loader.load();
  }
  // Icon glyphs: without the font every Material icon renders as a box.
  final root = Platform.environment['FLUTTER_ROOT'];
  if (root != null) {
    final icons = File(
        '$root/bin/cache/artifacts/material_fonts/MaterialIcons-Regular.otf');
    if (icons.existsSync()) {
      final bytes = icons.readAsBytesSync();
      final loader = FontLoader('MaterialIcons')
        ..addFont(Future.value(ByteData.sublistView(bytes)));
      await loader.load();
    }
  }
  _fontsLoaded = true;
}

/// Lets real asynchronous work (HTTP mocks, timers) finish between frames.
Future<void> settleAsync(WidgetTester tester) async {
  for (var i = 0; i < 8; i++) {
    await tester
        .runAsync(() => Future<void>.delayed(const Duration(milliseconds: 2)));
    await tester.pump(const Duration(milliseconds: 50));
  }
  await tester.pumpAndSettle();
}

/// Applies [viewport] (and an optional keyboard inset and text scale) to the
/// test view. Call [WidgetTester.view]'s reset through [addTearDown].
void useViewport(
  WidgetTester tester,
  AuditViewport viewport, {
  double keyboard = 0,
  double textScale = 1,
}) {
  const ratio = 2.0;
  tester.view
    ..devicePixelRatio = ratio
    ..physicalSize = viewport.size * ratio
    ..padding = FakeViewPadding(
        top: viewport.top * ratio, bottom: viewport.bottom * ratio)
    ..viewPadding = FakeViewPadding(
        top: viewport.top * ratio, bottom: viewport.bottom * ratio)
    ..viewInsets = FakeViewPadding(bottom: keyboard * ratio);
  tester.platformDispatcher.textScaleFactorTestValue = textScale;
  addTearDown(() {
    tester.view.reset();
    tester.platformDispatcher.clearTextScaleFactorTestValue();
  });
}

/// Writes a PNG of the whole test view when `AUDIT_DIR` is set; otherwise does
/// nothing, so ordinary test runs stay side-effect free.
///
/// With [design] set (an M-number) the approved export is placed to the left of
/// the render so both can be compared in one picture.
Future<void> captureAudit(WidgetTester tester, GlobalKey boundary, String name,
    {int? design}) async {
  final dir = Platform.environment['AUDIT_DIR'];
  if (dir == null || dir.isEmpty) return;
  await tester.runAsync(() async {
    final render =
        boundary.currentContext!.findRenderObject()! as RenderRepaintBoundary;
    var image = await render.toImage(pixelRatio: 1);
    if (design != null) {
      final tag = 'M-${design.toString().padLeft(3, '0')}';
      final matches = Directory('../../docs/designed')
          .listSync(recursive: true)
          .whereType<File>()
          .where((f) => f.path.contains(tag) && f.path.endsWith('.png'));
      if (matches.isNotEmpty) {
        final reference =
            await decodeImageFromList(matches.first.readAsBytesSync());
        final height =
            reference.height > image.height ? reference.height : image.height;
        final recorder = ui.PictureRecorder();
        final canvas = Canvas(recorder);
        canvas.drawRect(
            Rect.fromLTWH(0, 0, (reference.width + image.width + 12).toDouble(),
                height.toDouble()),
            Paint()..color = const Color(0xFF888888));
        canvas.drawImage(reference, Offset.zero, Paint());
        canvas.drawImage(image, Offset(reference.width + 12.0, 0), Paint());
        image = await recorder
            .endRecording()
            .toImage(reference.width + image.width + 12, height);
      }
    }
    final data = await image.toByteData(format: ui.ImageByteFormat.png);
    final file = File('$dir/$name.png');
    await file.parent.create(recursive: true);
    await file.writeAsBytes(data!.buffer.asUint8List());
  });
}

/// Like [settleAsync] but never waits for animations to stop, for screens
/// that legitimately animate forever (buffering indicators, players).
Future<void> settleBounded(WidgetTester tester) async {
  for (var i = 0; i < 10; i++) {
    await tester
        .runAsync(() => Future<void>.delayed(const Duration(milliseconds: 2)));
    await tester.pump(const Duration(milliseconds: 50));
  }
}
