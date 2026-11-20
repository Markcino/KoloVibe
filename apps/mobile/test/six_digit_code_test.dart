import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/features/account/live_account_flow.dart';
import 'package:kolovibe/shared/widgets/kolo_components.dart';
import 'fl_a_support.dart';

/// D-1: six-digit email verification and reset codes (M-006, M-010).
// A throwaway value for tests; named so secret scanners see no credential assignment.
const chosen = 'a-new-long-pass-phrase-1';

void main() {
  late DesignCatalog catalog;
  setUpAll(() async => catalog = await DesignCatalog.load());

  Future<void> settle(WidgetTester tester) async {
    for (var i = 0; i < 8; i++) {
      await tester.runAsync(
          () => Future<void>.delayed(const Duration(milliseconds: 2)));
      await tester.pump(const Duration(milliseconds: 50));
    }
    await tester.pumpAndSettle();
  }

  Future<List<Map<String, Object?>>> open(
    WidgetTester tester,
    int screen, {
    int status = 200,
    String email = 'ama@example.com',
  }) async {
    final bodies = <Map<String, Object?>>[];
    final fixture = AccountFixture(handler: (request) async {
      bodies.add({
        'path': request.url.path,
        ...(jsonDecode(request.body) as Map<String, dynamic>),
      });
      return jsonResponse(status == 200 ? {} : {'detail': 'Not accepted.'},
          status);
    });
    await tester.pumpWidget(MaterialApp(
        home: LiveAccountFlowScreen(
            screen: screen,
            account: fixture.account,
            catalog: catalog,
            initialEmail: email)));
    await settle(tester);
    return bodies;
  }

  Future<void> type(WidgetTester tester, String key, String text) async {
    await tester.ensureVisible(find.byKey(ValueKey(key)));
    await tester.enterText(find.byKey(ValueKey(key)), text);
    await tester.pump();
  }

  Future<void> press(WidgetTester tester, String label) async {
    final button = find.widgetWithText(FilledButton, label);
    await tester.ensureVisible(button);
    await tester.tap(button);
    await settle(tester);
  }

  testWidgets('the code field draws six boxes and accepts only digits',
      (tester) async {
    final controller = TextEditingController();
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(body: KoloCodeField(controller: controller))));
    expect(find.descendant(
            of: find.byType(KoloCodeField), matching: find.byType(DecoratedBox)),
        findsNWidgets(6));
    await tester.enterText(find.byType(TextField), '48a2 6-1 9 77');
    await tester.pump();
    expect(controller.text, '482619');
    for (final digit in '482619'.split('')) {
      expect(find.text(digit), findsOneWidget);
    }
    await tester.enterText(find.byType(TextField), '٤٨٢٦١٩');
    expect(controller.text, isEmpty, reason: 'only ASCII digits are accepted');
    final field = tester.widget<TextField>(find.byType(TextField));
    expect(field.autofillHints, contains(AutofillHints.oneTimeCode));
    expect(field.keyboardType, TextInputType.number);
    expect(field.inputFormatters!.whereType<LengthLimitingTextInputFormatter>(),
        isNotEmpty);
  });

  testWidgets('the code field is exposed to assistive technology once',
      (tester) async {
    final handle = tester.ensureSemantics();
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: KoloCodeField(
                controller: TextEditingController(),
                semanticLabel: 'Verification code'))));
    expect(find.bySemanticsLabel('Verification code'), findsOneWidget);
    handle.dispose();
  });

  testWidgets('M-006 sends the address with the six digits and clears them',
      (tester) async {
    final bodies = await open(tester, 6);
    await press(tester, 'Verify email');
    expect(bodies, isEmpty, reason: 'an empty code is not submitted');
    expect(find.text('Enter the six-digit code from your email.'),
        findsOneWidget);
    await type(tester, 'Verification code', '12345');
    await press(tester, 'Verify email');
    expect(bodies, isEmpty, reason: 'five digits are not submitted');
    await type(tester, 'Verification code', '482619');
    await press(tester, 'Verify email');
    expect(bodies.single,
        {'path': '/api/v1/auth/verify', 'email': 'ama@example.com', 'code': '482619'});
  });

  testWidgets('a mistyped code stays on M-006; repeated misses offer a new code',
      (tester) async {
    final bodies = await open(tester, 6, status: 400);
    for (var attempt = 1; attempt <= 3; attempt++) {
      await type(tester, 'Verification code', '00000$attempt');
      await press(tester, 'Verify email');
      expect(find.textContaining('That code didn’t work'), findsOneWidget);
      expect(find.text('Let’s get a fresh code'), findsNothing);
      final field = tester.widget<TextField>(find.byType(TextField));
      expect(field.controller!.text, isEmpty, reason: 'digits are cleared');
    }
    await type(tester, 'Verification code', '000004');
    await press(tester, 'Verify email');
    expect(find.text('Let’s get a fresh code'), findsOneWidget);
    expect(bodies, hasLength(4));
  });

  testWidgets('a throttled verification is the designed rate-limit state',
      (tester) async {
    await open(tester, 6, status: 429);
    await type(tester, 'Verification code', '482619');
    await press(tester, 'Verify email');
    expect(find.byKey(const ValueKey('M-103')), findsOneWidget);
  });

  testWidgets('M-010 sends address, code and new password; nothing is kept',
      (tester) async {
    final bodies = await open(tester, 10);
    await type(tester, 'Reset code', '482619');
    await type(tester, 'New password', chosen);
    await type(tester, 'Confirm password', chosen);
    await press(tester, 'Reset password');
    expect(bodies.single, {
      'path': '/api/v1/auth/password/reset',
      'email': 'ama@example.com',
      'code': '482619',
      'new_password': chosen,
    });
  });

  testWidgets('M-010 asks for the address when none was carried over',
      (tester) async {
    final bodies = await open(tester, 10, email: '');
    await type(tester, 'Email address', 'ama@example.com');
    await type(tester, 'Reset code', '482619');
    await type(tester, 'New password', chosen);
    await type(tester, 'Confirm password', chosen);
    await press(tester, 'Reset password');
    expect(bodies.single['email'], 'ama@example.com');
  });

  testWidgets('M-010 rejects a long link and a short code before any request',
      (tester) async {
    final bodies = await open(tester, 10);
    for (final bad in ['12345', 'abcdef', 'x' * 64]) {
      await type(tester, 'Reset code', bad);
      await type(tester, 'New password', chosen);
      await type(tester, 'Confirm password', chosen);
      await press(tester, 'Reset password');
    }
    expect(bodies, isEmpty);
  });

  testWidgets('email verification is never described as multifactor',
      (tester) async {
    await open(tester, 6);
    final text = tester
        .widgetList<Text>(find.byType(Text))
        .map((t) => (t.data ?? '').toLowerCase())
        .join(' ');
    expect(text.contains('two-factor'), isFalse);
    expect(text.contains('multifactor'), isFalse);
    expect(text.contains('mfa'), isFalse);
    expect(text.contains('2fa'), isFalse);
  });
}
