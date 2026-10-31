import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/app/kolovibe_app.dart';
import 'package:kolovibe/core/presentation/design_node.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late DesignCatalog catalog;
  setUpAll(() async => catalog = await DesignCatalog.load());

  Future<void> boot(WidgetTester tester, int id) async {
    await tester.pumpWidget(KoloVibeApp(catalog: catalog, initialScreen: id));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
  }

  testWidgets('Sign-in fails closed and clears the password field',
      (tester) async {
    await boot(tester, 4);
    await tester.enterText(
        find.byType(TextFormField).at(0), 'user@example.com');
    await tester.enterText(find.byType(TextFormField).at(1), 'transient-input');
    await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
    await tester.pump();
    expect(find.textContaining('No request was submitted.'), findsWidgets);
    final password =
        tester.widgetList<EditableText>(find.byType(EditableText)).last;
    expect(password.controller.text, isEmpty);
    expect(find.text('This service is not connected yet.'), findsNothing);
  });

  testWidgets('Account registration validates input before any submission',
      (tester) async {
    await boot(tester, 5);
    await tester.tap(find.widgetWithText(FilledButton, 'Create account'));
    await tester.pump();
    expect(find.textContaining('Enter'), findsWidgets);
    expect(find.text('Verify your email'), findsNothing);
  });

  testWidgets('Protected account and points surfaces fail closed',
      (tester) async {
    for (final id in [17, 37, 61, 79]) {
      await boot(tester, id);
      expect(find.text('This service is not connected yet.'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
    }
  });
}
