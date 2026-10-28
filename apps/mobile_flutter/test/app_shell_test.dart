import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/app/app_dependencies.dart';
import 'package:kolovibe/app/kolovibe_app.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/demo/demo_repository.dart';
import 'package:kolovibe/features/shell/main_shell.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late DesignCatalog catalog;
  setUpAll(() async {
    catalog = await DesignCatalog.load();
  });
  testWidgets('Five primary destinations navigate to separate feature surfaces',
      (tester) async {
    await tester.pumpWidget(KoloVibeApp(
        catalog: catalog,
        initialScreen: 17,
        dependencies: AppDependencies.preview(DemoRepository().services)));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.byType(MainShell), findsOneWidget);
    final shell = find.byType(MainShell);
    for (final label in MainShell.labels) {
      expect(find.descendant(of: shell, matching: find.text(label)),
          findsOneWidget);
    }
    await tester.tap(find.descendant(of: shell, matching: find.text('Videos')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.text('For You'), findsOneWidget);
    expect(find.text('Following'), findsOneWidget);
    expect(
        find.textContaining('Video playback is not connected'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
}
