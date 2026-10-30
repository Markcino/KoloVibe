import 'package:flutter/material.dart';
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
  });
  Future<void> boot(WidgetTester tester, int id, {bool demo = true}) async {
    await tester.pumpWidget(KoloVibeApp(
        catalog: catalog,
        initialScreen: id,
        dependencies: demo
            ? AppDependencies.preview(DemoRepository().services)
            : const AppDependencies.unavailable()));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pump(const Duration(milliseconds: 400));
  }

  Future<void> tap(WidgetTester tester, String label) async {
    final button = find.widgetWithText(FilledButton, label);
    await tester.ensureVisible(button);
    await tester.tap(button);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 250));
    await tester.pump(const Duration(milliseconds: 400));
  }

  testWidgets('Demo registration and verification lead to profile setup',
      (tester) async {
    await boot(tester, 5);
    final fields = find.byType(TextFormField);
    await tester.enterText(fields.at(0), 'Demo Viewer');
    await tester.enterText(fields.at(1), 'viewer@example.com');
    await tester.enterText(fields.at(2), 'temporary-test-input');
    await tester.tap(find.byType(CheckboxListTile));
    await tester.pump();
    await tap(tester, 'Create account');
    expect(find.text('Verify your email'), findsOneWidget);
    await tester.enterText(
        find.byKey(const ValueKey('verificationCode')), '123456');
    await tap(tester, 'Verifying…');
    expect(find.text('Make it yours'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets('Normal sign-in fails closed and clears password buffer',
      (tester) async {
    await boot(tester, 4, demo: false);
    await tester.enterText(
        find.byType(TextFormField).at(0), 'viewer@example.com');
    await tester.enterText(
        find.byType(TextFormField).at(1), 'temporary-test-input');
    await tap(tester, 'Sign in');
    expect(find.textContaining('No request was submitted.'), findsWidgets);
    final editable =
        tester.widgetList<EditableText>(find.byType(EditableText)).last;
    expect(editable.controller.text, isEmpty);
    expect(find.textContaining('DEMO ·'), findsNothing);
  });
  testWidgets('Changing a profile requires confirmation before back navigation',
      (tester) async {
    await boot(tester, 39);
    await tester.enterText(find.byType(TextFormField).first, 'Changed name');
    await tester.tap(find.bySemanticsLabel('Back'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.text('Keep your changes?'), findsOneWidget);
    await tester.tap(find.text('Keep editing'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.text('Changed name'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets('Deletion requires deliberate acknowledgment and DELETE',
      (tester) async {
    await boot(tester, 92);
    await tap(tester, 'Confirm deletion request');
    expect(find.text('Type DELETE to acknowledge.'), findsWidgets);
    await tester.enterText(find.byType(TextFormField).first, 'DELETE');
    await tester.tap(find.byType(CheckboxListTile));
    await tester.pump();
    await tap(tester, 'Confirm deletion request');
    expect(find.text('Deletion request received'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets('Video deletion dialog requires the exact confirmation',
      (tester) async {
    await boot(tester, 56);
    final confirmation = find.byType(TextFormField).last;
    await tap(tester, 'Delete video');
    expect(find.textContaining('Type DELETE'), findsWidgets);
    await tester.enterText(confirmation, 'delete');
    await tap(tester, 'Delete video');
    expect(find.textContaining('Type DELETE'), findsWidgets);
    await tester.enterText(confirmation, 'DELETE');
    await tap(tester, 'Delete video');
    expect(find.text('My video library'), findsWidgets);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets('Expired-session sign-in returns to Creator Studio',
      (tester) async {
    await boot(tester, 101);
    await tap(tester, 'Sign in again');
    await tester.enterText(
        find.byType(TextFormField).at(0), 'viewer@example.com');
    await tester.enterText(
        find.byType(TextFormField).at(1), 'temporary-test-input');
    await tap(tester, 'Sign in');
    expect(find.text('Creator Studio'), findsWidgets);
    expect(find.text('Good stories travel.'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
}
