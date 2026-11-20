import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/features/account/live_account_flow.dart';
import 'package:kolovibe/features/account/live_account_repository.dart';
import 'package:kolovibe/features/account/live_account_screen.dart';
import 'package:kolovibe/features/account/account_sessions_screen.dart';
import 'package:kolovibe/features/settings/live_information_screen.dart';
import 'package:kolovibe/features/settings/live_settings_repository.dart';
import 'package:kolovibe/features/settings/live_settings_screen.dart';
import 'package:kolovibe/features/system/system_ui.dart';
import 'package:kolovibe/app/screen_route.dart';
import 'fl_a_support.dart';

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

  Future<void> enter(WidgetTester tester, String label, String value) async {
    final finder = find.byKey(ValueKey(label));
    await tester.ensureVisible(finder);
    await tester.enterText(finder, value);
  }

  Future<void> tap(WidgetTester tester, String text) async {
    final buttons = find.ancestor(
        of: find.text(text),
        matching:
            find.byWidgetPredicate((widget) => widget is ButtonStyleButton));
    final finder =
        buttons.evaluate().isNotEmpty ? buttons.last : find.text(text).last;
    await tester.ensureVisible(finder);
    await tester.tap(finder);
    await settle(tester);
  }

  Widget app(Widget child) => MaterialApp(
      key: UniqueKey(),
      home: child,
      onGenerateRoute: (settings) => MaterialPageRoute<void>(
          settings: settings,
          builder: (_) =>
              Scaffold(body: Text('Destination ${settings.name}'))));
  Future<AccountFixture> form(WidgetTester tester, int id,
      {int? failure, bool offline = false}) async {
    final fixture = AccountFixture(handler: (request) async {
      if (offline) throw http.ClientException('Offline');
      if (failure != null) {
        return jsonResponse({'detail': 'Action was not accepted.'}, failure);
      }
      if (request.url.path.endsWith('/auth/login')) {
        return jsonResponse(
            {'access_token': 'access', 'refresh_token': 'new-refresh'});
      }
      if (request.url.path.endsWith('/reauthenticate')) {
        return jsonResponse(proofData);
      }
      return jsonResponse({});
    });
    await tester.pumpWidget(app(LiveAccountFlowScreen(
        screen: id,
        account: fixture.account,
        catalog: catalog,
        initialEmail: 'mark@example.test')));
    await settle(tester);
    return fixture;
  }

  Future<void> fill(WidgetTester tester, int id) async {
    if ({5}.contains(id)) {
      await enter(tester, 'Full name', 'Mark');
      await enter(tester, 'Password', 'typed value'.padRight(32, 'x'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.byType(CheckboxListTile));
      await tester.pumpAndSettle();
      await tester.tap(find.byType(CheckboxListTile));
      await tester.pumpAndSettle();
    }
    if ({4, 15}.contains(id)) {
      await enter(tester, 'Password', 'typed value'.padRight(32, 'x'));
    }
    if (id == 6) {
      await enter(tester, 'Verification code', 'c'.padRight(40, 'x'));
    }
    if (id == 10) await enter(tester, 'Reset code', 'c'.padRight(40, 'x'));
    if ({10, 82}.contains(id)) {
      await enter(tester, 'New password', 'typed value'.padRight(32, 'x'));
      await enter(tester, 'Confirm password', 'typed value'.padRight(32, 'x'));
    }
    if ({16, 82}.contains(id)) {
      await enter(tester, 'Current password', 'typed value'.padRight(32, 'x'));
    }
    if ({13, 80}.contains(id)) {
      await enter(tester, 'Display name', 'Mark Updated');
    }
  }

  final actions = {
    4: 'Sign in',
    5: 'Create account',
    6: 'Verify email',
    7: 'Request a new code',
    8: 'Request a new code',
    9: 'Send reset instructions',
    10: 'Reset password',
    13: 'Continue to KoloVibe',
    15: 'Try signing in again',
    16: 'Verify identity',
    80: 'Save changes',
    82: 'Change password'
  };
  final targets = {
    4: 79,
    5: 6,
    6: 4,
    8: 7,
    9: 10,
    10: 11,
    13: 17,
    15: 79,
    16: 79,
    80: 79
  };
  for (final entry in actions.entries) {
    testWidgets('M-${entry.key} live action succeeds and clears secrets',
        (tester) async {
      final fixture = await form(tester, entry.key);
      await fill(tester, entry.key);
      await tap(tester, entry.value);

      if (entry.key == 7) {
        expect(find.textContaining('If eligible, you will receive a new code.'),
            findsOneWidget);
      } else if (entry.key == 9) {
        // The designed "Check your email" state stays on the screen and offers
        // the reset-code step.
        expect(find.text('Check your email'), findsOneWidget);
        expect(find.text('Enter reset code'), findsOneWidget);
      } else if (entry.key == 82) {
        expect(find.text('Password updated'), findsOneWidget);
      } else if ({6, 7, 4, 10, 11}.contains(targets[entry.key])) {
        expect(
            find.byKey(ValueKey(
                'live-M-${targets[entry.key].toString().padLeft(3, '0')}')),
            findsOneWidget);
      } else {
        expect(
            find.text('Destination ${ScreenRoute(targets[entry.key]!).name}'),
            findsOneWidget);
      }
      expect(fixture.requests.length, greaterThan(0));
      for (final element
          in tester.widgetList<TextField>(find.byType(TextField))) {
        if (element.obscureText) expect(element.controller!.text, isEmpty);
      }
    });
    for (final status in [400, 401, 403, 409, 429, 503, 0]) {
      testWidgets(
          'M-${entry.key} presents failure $status without retaining secrets',
          (tester) async {
        await form(tester, entry.key,
            failure: status == 0 ? null : status, offline: status == 0);
        await fill(tester, entry.key);
        await tap(tester, entry.value);
        final system =
            {403: 'M-100', 429: 'M-103', 503: 'M-102', 0: 'M-095'}[status];
        if (status == 429 && {7, 8}.contains(entry.key)) {
          // A throttled resend is the designed "Resend unavailable" state.
          expect(find.text('Resend unavailable'), findsOneWidget);
          expect(
              find.text('Another request isn’t available yet'), findsOneWidget);
        } else if (system != null) {
          expect(find.byKey(ValueKey(system)), findsOneWidget);
        } else if (status == 401 && {13, 16, 80, 82}.contains(entry.key)) {
          expect(find.byKey(const ValueKey('M-101')), findsOneWidget);
        } else if (entry.key == 5 && status == 409) {
          expect(
              find.textContaining('This email can’t be used'), findsOneWidget);
        } else if ({4, 15}.contains(entry.key) && {400, 401}.contains(status)) {
          expect(find.text('We couldn’t\nsign you in.'), findsOneWidget);
        } else if (entry.key == 6 && status == 400) {
          expect(find.text('Let’s get a fresh code'), findsOneWidget);
        } else {
          expect(find.text('Action was not accepted.'), findsOneWidget);
        }
        for (final element
            in tester.widgetList<TextField>(find.byType(TextField))) {
          if (element.obscureText) expect(element.controller!.text, isEmpty);
        }
      });
    }
  }
  testWidgets(
      'M-016 returns proof to caller only after successful live confirmation',
      (tester) async {
    final fixture =
        AccountFixture(handler: (_) async => jsonResponse(proofData));
    Reauthentication? returned;
    await tester.pumpWidget(app(Builder(
        builder: (context) => FilledButton(
            onPressed: () async => returned =
                await confirmIdentity(context, fixture.account, catalog),
            child: const Text('Sensitive action')))));
    await tap(tester, 'Sensitive action');
    await fill(tester, 16);
    await tap(tester, 'Verify identity');
    expect(returned?.available, isTrue);
    expect(find.text('Sensitive action'), findsOneWidget);
    returned?.dispose();
  });
  testWidgets(
      'profile email is read-only, photo action is honest, unsaved form guarded',
      (tester) async {
    await form(tester, 80);
    expect(
        tester
            .widget<TextField>(find.descendant(
                of: find.byKey(const ValueKey('Account email')),
                matching: find.byType(TextField)))
            .readOnly,
        isTrue);
    await tap(tester, 'Change photo');
    expect(find.textContaining('Profile photos are not available yet.'),
        findsOneWidget);
    await enter(tester, 'Display name', 'Unsaved');
    await tap(tester, 'Cancel');
    expect(find.byKey(const ValueKey('M-105')), findsOneWidget);
    await tap(tester, 'Keep editing');
    expect(find.byKey(const ValueKey('live-M-080')), findsOneWidget);
    await tap(tester, 'Cancel');
    await tap(tester, 'Discard changes');
    expect(
        find.text('Destination ${const ScreenRoute(79).name}'), findsOneWidget);
  });
  testWidgets('M-079 uses live identity and creator roles', (tester) async {
    await tester.pumpWidget(app(LiveAccountScreen(
        repository: AccountFixture().account, catalog: catalog)));
    await settle(tester);
    expect(find.text('mark@example.test'), findsOneWidget);
    expect(find.text('Roles: user, creator'), findsOneWidget);
    expect(find.text('Creator studio'), findsOneWidget);
    await tap(tester, 'Account settings');
    expect(
        find.text('Destination ${const ScreenRoute(81).name}'), findsOneWidget);
  });
  testWidgets('M-079 links to the live account status (M-077)', (tester) async {
    await tester.pumpWidget(app(LiveAccountScreen(
        repository: AccountFixture().account, catalog: catalog)));
    await settle(tester);
    await tap(tester, 'Account status');
    expect(
        find.text('Destination ${const ScreenRoute(77).name}'), findsOneWidget);
  });
  testWidgets('M-083 revocation confirms then reloads server records',
      (tester) async {
    var revoked = false;
    final fixture = AccountFixture(handler: (request) async {
      if (request.method == 'DELETE') {
        revoked = true;
        return http.Response('', 204);
      }
      return jsonResponse({
        'items': [
          {
            'id': accountId,
            'created_at': '2026-11-11T12:00:00Z',
            'expires_at': '2026-12-11T12:00:00Z',
            'current': true
          },
          if (!revoked)
            {
              'id': receiptId,
              'created_at': '2026-11-10T12:00:00Z',
              'expires_at': '2026-12-11T12:00:00Z',
              'current': false
            }
        ]
      });
    });
    await tester
        .pumpWidget(app(AccountSessionsScreen(repository: fixture.account)));
    await settle(tester);
    await tap(tester, 'End session');
    expect(find.byKey(const ValueKey('M-106')), findsOneWidget);
    expect(revoked, isFalse);
    await tap(tester, 'End session');
    expect(revoked, isTrue);
    expect(find.text('Signed-in session'), findsNothing);
    expect(find.text('Current session'), findsOneWidget);
  });
  testWidgets(
      'deletion receipt shows exact id, status and date, existing request acknowledged',
      (tester) async {
    final fixture = AccountFixture();
    await tester.pumpWidget(app(LiveSettingsScreen(
        route: const ScreenRoute(93),
        catalog: catalog,
        repository: LiveSettingsRepository(fixture.account),
        account: fixture.account,
        receipt: PrivacyReceipt(
            receiptId, 'deletion', 'in_review', DateTime.utc(2026, 11, 11),
            existing: true))));
    await settle(tester);
    expect(find.text('Your existing request'), findsOneWidget);
    expect(find.text('Request ID: $receiptId'), findsOneWidget);
    expect(find.text('Status: in review'), findsOneWidget);
    expect(find.text('Created: 2026-11-11T00:00:00.000Z'), findsOneWidget);
  });
  testWidgets('M-092 intake uses proof and does not disable or sign out',
      (tester) async {
    final fixture = AccountFixture(handler: (request) async {
      expect(request.url.path, '/api/v1/me/privacy-requests');
      expect(request.body.contains('reauth_token'), isTrue);
      expect(request.body.contains('current_password'), isFalse);
      return jsonResponse(privacyData('deletion'), 201);
    });
    await tester.pumpWidget(app(LiveSettingsScreen(
        route: const ScreenRoute(92),
        catalog: catalog,
        repository: LiveSettingsRepository(fixture.account),
        account: fixture.account,
        proof: Reauthentication(
            transientProof, DateTime.now().add(const Duration(minutes: 5))))));
    await settle(tester);
    await tester.enterText(find.byType(TextField), 'DELETE');
    await tester.tap(find.byType(CheckboxListTile));
    await tap(tester, 'Confirm deletion request');
    expect(find.text('Request ID: $receiptId'), findsOneWidget);
    expect(fixture.store.value, 'rotated-refresh');
  });
  for (final id in [14, 81, 87, 88, 89, 90]) {
    testWidgets(
        'M-$id static/settings content has no sample account or unconfigured links',
        (tester) async {
      await tester.pumpWidget(app(LiveInformationScreen(
          screen: id,
          catalog: catalog,
          account: AccountFixture().account,
          device: TestDevice())));
      await settle(tester);
      expect(find.textContaining('Ama'), findsNothing);
      expect(find.text('View available support options'), findsNothing);
      expect(tester.takeException(), isNull);
    });
  }
  testWidgets('M-090 successful logout routes to welcome with cleared session',
      (tester) async {
    final fixture =
        AccountFixture(handler: (_) async => http.Response('', 204));
    await tester.pumpWidget(app(LiveInformationScreen(
        screen: 90,
        catalog: catalog,
        account: fixture.account,
        device: TestDevice())));
    await settle(tester);
    await tap(tester, 'Sign out');
    expect(fixture.store.value, isNull);
    expect(
        find.text('Destination ${const ScreenRoute(2).name}'), findsOneWidget);
  });
  testWidgets(
      'privacy access and deletion reuse M-016 and display existing receipt',
      (tester) async {
    for (final kind in ['access', 'deletion']) {
      final fixture = AccountFixture(handler: (request) async {
        if (request.url.path.endsWith('/reauthenticate')) {
          return jsonResponse(proofData);
        }
        if (request.method == 'POST') {
          return jsonResponse({'code': 'request_open'}, 409);
        }
        return jsonResponse({
          'items': [privacyData(kind, 'in_review')]
        });
      });
      await tester.pumpWidget(app(LiveSettingsScreen(
          key: ValueKey(kind),
          route: ScreenRoute(kind == 'access' ? 84 : 91),
          catalog: catalog,
          repository: LiveSettingsRepository(fixture.account),
          account: fixture.account)));
      await settle(tester);
      await tap(
          tester,
          kind == 'access'
              ? 'Request account data'
              : 'Verify identity to continue');
      await fill(tester, 16);
      await tap(tester, 'Verify identity');
      if (kind == 'deletion') {
        await tester.enterText(find.byType(TextField), 'DELETE');
        await tester.tap(find.byType(CheckboxListTile));
        await tap(tester, 'Confirm deletion request');
      }
      expect(find.text('Your existing request'), findsOneWidget);
      expect(find.text('Status: in review'), findsOneWidget);
      expect(find.text('Request ID: $receiptId'), findsOneWidget);
    }
  });
  testWidgets(
      'inline deletion wrong password is generic and controller is cleared',
      (tester) async {
    final fixture = AccountFixture(
        handler: (_) async =>
            jsonResponse({'detail': 'Identity could not be confirmed.'}, 400));
    await tester.pumpWidget(app(LiveSettingsScreen(
        route: const ScreenRoute(92),
        catalog: catalog,
        repository: LiveSettingsRepository(fixture.account),
        account: fixture.account)));
    await settle(tester);
    final inputs = find.byType(TextField);
    await tester.enterText(inputs.first, 'DELETE');
    await tester.enterText(inputs.last, 'typed input');
    await tester.tap(find.byType(CheckboxListTile));
    await tap(tester, 'Confirm deletion request');
    expect(tester.widget<TextField>(inputs.last).controller!.text, isEmpty);
    await tester.drag(find.byType(ListView), const Offset(0, 600));
    await settle(tester);
    expect(find.textContaining('Identity confirmation was not accepted.'),
        findsOneWidget);
    expect(
        fixture.requests.where((r) => r.url.path.endsWith('/privacy-requests')),
        isEmpty);
  });
  testWidgets(
      'notification switches persist preferences and device settings are native',
      (tester) async {
    final device = TestDevice();
    var updates = 0;
    final fixture = AccountFixture(handler: (request) async {
      if (request.method == 'PATCH') {
        updates++;
        return http.Response(request.body, 200);
      }
      return jsonResponse(
          {'email_notifications': false, 'push_notifications': false});
    });
    await tester.pumpWidget(app(LiveSettingsScreen(
        route: const ScreenRoute(86),
        catalog: catalog,
        repository: LiveSettingsRepository(fixture.account),
        account: fixture.account,
        device: device)));
    await settle(tester);
    await tester.tap(find.byType(SwitchListTile).first);
    await settle(tester);
    expect(updates, 1);
    expect(
        tester.widget<SwitchListTile>(find.byType(SwitchListTile).first).value,
        isTrue);
    expect(find.text('Device notifications are off'), findsNothing);
    await tap(tester, 'Open device settings');
    expect(device.settingsCalls, 1);
  });
  testWidgets('configured support link delegates HTTPS to DeviceBridge',
      (tester) async {
    final device = TestDevice();
    await tester.pumpWidget(app(LiveInformationScreen(
        screen: 89,
        catalog: catalog,
        account: AccountFixture().account,
        device: device,
        links: PublicLinks('https://web.example.test'))));
    await settle(tester);
    await tap(tester, 'View available support options');
    expect(device.urls.single.toString(), 'https://web.example.test/help');
  });
  for (final status in [400, 401, 403, 409, 429, 503, 0]) {
    testWidgets(
        'logout failure $status clears local session and offers welcome honestly',
        (tester) async {
      final fixture = AccountFixture(handler: (_) async {
        if (status == 0) throw http.ClientException('Offline');
        return jsonResponse({}, status);
      });
      await tester.pumpWidget(app(LiveInformationScreen(
          screen: 90,
          catalog: catalog,
          account: fixture.account,
          device: TestDevice())));
      await settle(tester);
      await tap(tester, 'Sign out');
      expect(fixture.store.value, isNull);
      expect(
          find.textContaining(
              'Server session revocation could not be confirmed.'),
          findsOneWidget);
      await tap(tester, 'Continue to welcome');
      expect(find.text('Destination ${const ScreenRoute(2).name}'),
          findsOneWidget);
    });
  }
  for (final status in [400, 401, 403, 409, 429, 503, 0]) {
    for (final action in ['preferences', 'revoke']) {
      testWidgets('$action presents live failure $status and allows recovery',
          (tester) async {
        final fixture = AccountFixture(handler: (request) async {
          if (request.method == 'GET') {
            if (action == 'preferences') {
              return jsonResponse(
                  {'email_notifications': false, 'push_notifications': false});
            }
            return jsonResponse({
              'items': [
                {
                  'id': receiptId,
                  'created_at': '2026-11-11T12:00:00Z',
                  'expires_at': '2026-12-11T12:00:00Z',
                  'current': false
                }
              ]
            });
          }
          if (status == 0) throw http.ClientException('Offline');
          return jsonResponse(
              {'detail': 'Could not complete the action.'}, status);
        });
        await tester.pumpWidget(app(action == 'preferences'
            ? LiveSettingsScreen(
                route: const ScreenRoute(86),
                catalog: catalog,
                repository: LiveSettingsRepository(fixture.account),
                account: fixture.account)
            : AccountSessionsScreen(repository: fixture.account)));
        await settle(tester);
        if (action == 'preferences') {
          await tester.tap(find.byType(SwitchListTile).first);
          await settle(tester);
        } else {
          await tap(tester, 'End session');
          await tap(tester, 'End session');
        }
        final screen = {
          400: 99,
          401: 101,
          403: 100,
          409: 99,
          429: 103,
          503: 102,
          0: 95
        }[status]!;
        expect(find.byKey(ValueKey('M-${screen.toString().padLeft(3, '0')}')),
            findsOneWidget);
        if (status == 401) {
          expect(fixture.store.value, isNull);
        } else {
          await tap(tester, 'Try again');
          expect(find.byKey(ValueKey('M-${screen.toString().padLeft(3, '0')}')),
              findsNothing);
        }
      });
    }
  }
}
