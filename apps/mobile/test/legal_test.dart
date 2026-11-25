// Decision B in the app: versioned legal texts, acceptance at registration, re-acceptance and marketing consent.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:kolovibe/app/screen_route.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/features/account/live_account_flow.dart';
import 'package:kolovibe/features/legal/legal_screens.dart';
import 'package:kolovibe/features/legal/live_legal_repository.dart';
import 'package:kolovibe/features/settings/live_settings_repository.dart';
import 'package:kolovibe/features/settings/live_settings_screen.dart';

import 'fl_a_support.dart';
import 'support/audit_harness.dart' show settleAsync;

Map<String, dynamic>? body(http.Request request) => request.body.isEmpty
    ? null
    : jsonDecode(request.body) as Map<String, dynamic>;

void main() {
  late DesignCatalog catalog;
  setUpAll(() async => catalog = await DesignCatalog.load());

  group('repository', () {
    test('a document is read without a credential and parsed strictly',
        () async {
      final fixture = AccountFixture(
          handler: (r) async =>
              jsonResponse(legalDocument(r.url.pathSegments.last)));
      final legal = LiveLegalRepository(fixture.account);
      final document = await legal.document('terms');
      expect(document.summary.pendingLegalReview, isTrue);
      expect(document.summary.version, '2026-11-25');
      final sent = fixture.requests.single;
      expect([sent.method, sent.url.path], ['GET', '/api/v1/legal/terms']);
      expect(sent.headers.containsKey('Authorization'), isFalse);
      expect(() => legal.document('cookies'), throwsArgumentError);
    });

    test('an unexpected document or state is refused', () async {
      final broken = <Map<String, Object?>>[
        {...legalDocument('privacy')},
        {...legalDocument('terms'), 'status': 'final'},
        {...legalDocument('terms'), 'sha256': 'x'},
        {...legalDocument('terms'), 'extra': 1},
        {...legalDocument('terms'), 'text': ''},
      ];
      for (final answer in broken) {
        final legal = LiveLegalRepository(
            AccountFixture(handler: (_) async => jsonResponse(answer)).account);
        await expectLater(legal.document('terms'), throwsFormatException);
      }
      final state = legalState();
      for (final answer in [
        {...state, 'extra': 1},
        {...state, 'documents': (state['documents'] as List).reversed.toList()},
        {...state, 'acceptance_required': 'yes'},
        {
          ...state,
          'marketing': {'granted': true}
        },
      ]) {
        final legal = LiveLegalRepository(
            AccountFixture(handler: (_) async => jsonResponse(answer)).account);
        await expectLater(legal.state(), throwsFormatException);
      }
    });

    test('accepting and marketing send exactly the shown versions', () async {
      final fixture =
          AccountFixture(handler: (_) async => jsonResponse(legalState()));
      final legal = LiveLegalRepository(fixture.account);
      await legal.accept({'terms': '2026-11-25', 'privacy': '2026-11-25'});
      var sent = fixture.requests.last;
      expect([sent.method, sent.url.path], ['POST', '/api/v1/me/legal']);
      expect(body(sent), {
        'accepted': {'terms': '2026-11-25', 'privacy': '2026-11-25'}
      });
      expect(sent.headers['Authorization'], 'Bearer access');
      await legal.setMarketing(true, '2026-11-25');
      sent = fixture.requests.last;
      expect([sent.method, sent.url.path],
          ['PUT', '/api/v1/me/marketing-consent']);
      expect(body(sent), {'granted': true, 'version': '2026-11-25'});
      expect(
          () => legal.accept({'marketing': '2026-11-25'}), throwsArgumentError);
      expect(() => legal.accept({}), throwsArgumentError);
    });
  });

  group('registration (M-005)', () {
    Future<AccountFixture> open(WidgetTester tester,
        {http.Response Function(http.Request)? register}) async {
      tester.view.physicalSize = const Size(1080, 4000);
      tester.view.devicePixelRatio = 2;
      addTearDown(tester.view.reset);
      final fixture = AccountFixture(handler: (request) async {
        if (request.url.path.contains('/legal/')) {
          return jsonResponse(legalDocument(request.url.pathSegments.last));
        }
        if (request.url.path.endsWith('/auth/register')) {
          return register?.call(request) ??
              jsonResponse(
                  {'id': accountId, 'verification_required': true}, 201);
        }
        return jsonResponse({});
      });
      await tester.pumpWidget(MaterialApp(
          home: LiveAccountFlowScreen(
              screen: 5,
              account: fixture.account,
              catalog: catalog,
              initialEmail: 'mark@example.test'),
          onGenerateRoute: (settings) => MaterialPageRoute<void>(
              settings: settings,
              builder: (_) =>
                  Scaffold(body: Text('Destination ${settings.name}')))));
      await settleAsync(tester);
      return fixture;
    }

    Future<void> fill(WidgetTester tester,
        {bool accept = true, bool marketing = false}) async {
      await tester.enterText(find.byKey(const ValueKey('Full name')), 'Mark');
      await tester.enterText(find.byKey(const ValueKey('Password')), 'q' * 24);
      for (final (key, on) in [
        ('accept-legal', accept),
        ('marketing-consent', marketing)
      ]) {
        if (!on) continue;
        await tester.ensureVisible(find.byKey(ValueKey(key)));
        await tester.pumpAndSettle();
        await tester.tap(find.byKey(ValueKey(key)));
        await tester.pumpAndSettle();
      }
    }

    Future<void> create(WidgetTester tester) async {
      final button = find.widgetWithText(FilledButton, 'Create account');
      await tester.ensureVisible(button);
      await tester.tap(button);
      await settleAsync(tester);
    }

    Iterable<http.Request> registrations(AccountFixture f) =>
        f.requests.where((r) => r.url.path.endsWith('/auth/register'));

    testWidgets(
        'the current versions are shown, with the pending-review note and both texts to read',
        (tester) async {
      await open(tester);
      expect(
          find.byKey(const ValueKey('legal-pending-review')), findsOneWidget);
      expect(find.textContaining('Terms of Service (version 2026-11-25)'),
          findsOneWidget);
      expect(find.byKey(const ValueKey('read-terms')), findsOneWidget);
      expect(find.byKey(const ValueKey('read-privacy')), findsOneWidget);
      final marketing = tester.widget<CheckboxListTile>(
          find.byKey(const ValueKey('marketing-consent')));
      expect(marketing.value, isFalse,
          reason: 'marketing is off unless chosen');
    });

    testWidgets(
        'registration sends the accepted versions, and marketing only when chosen',
        (tester) async {
      final fixture = await open(tester);
      await fill(tester);
      await create(tester);
      expect(body(registrations(fixture).single), {
        'email': 'mark@example.test',
        'password': 'q' * 24,
        'display_name': 'Mark',
        'accepted': {'terms': '2026-11-25', 'privacy': '2026-11-25'},
        'marketing_consent': false,
      });
    });

    testWidgets('a chosen marketing consent is sent as true', (tester) async {
      final fixture = await open(tester);
      await fill(tester, marketing: true);
      await create(tester);
      expect(body(registrations(fixture).single)!['marketing_consent'], isTrue);
    });

    testWidgets('nothing is sent until the terms are accepted', (tester) async {
      final fixture = await open(tester);
      await fill(tester, accept: false);
      await create(tester);
      expect(registrations(fixture), isEmpty);
      expect(
          find.text(
              'Accept the Terms of Service and the Privacy Notice to continue.'),
          findsOneWidget);
    });

    testWidgets(
        'an outdated version is explained, unticked and the new version loaded',
        (tester) async {
      final fixture = await open(tester,
          register: (_) => jsonResponse(
              {'detail': 'x', 'code': 'legal_version_outdated'}, 409));
      final before =
          fixture.requests.where((r) => r.url.path.contains('/legal/')).length;
      await fill(tester);
      await create(tester);
      expect(
          find.textContaining('The terms were just updated'), findsOneWidget);
      expect(
          tester
              .widget<CheckboxListTile>(
                  find.byKey(const ValueKey('accept-legal')))
              .value,
          isFalse);
      expect(
          fixture.requests.where((r) => r.url.path.contains('/legal/')).length,
          greaterThan(before));
    });

    testWidgets('if the texts cannot be loaded, the account cannot be created',
        (tester) async {
      final fixture = AccountFixture(
          handler: (request) async => jsonResponse({'detail': 'down'}, 503));
      await tester.pumpWidget(MaterialApp(
          home: LiveAccountFlowScreen(
              screen: 5, account: fixture.account, catalog: catalog)));
      await settleAsync(tester);
      expect(find.byKey(const ValueKey('legal-retry')), findsOneWidget);
      expect(
          tester
              .widget<CheckboxListTile>(
                  find.byKey(const ValueKey('accept-legal')))
              .onChanged,
          isNull);
    });
  });

  group('reader', () {
    testWidgets('shows the version, the pending-review note and the text',
        (tester) async {
      final fixture = AccountFixture(
          handler: (r) async =>
              jsonResponse(legalDocument(r.url.pathSegments.last)));
      await tester.pumpWidget(MaterialApp(
          home: LegalDocumentScreen(
              repository: LiveLegalRepository(fixture.account),
              kind: 'privacy')));
      await settleAsync(tester);
      expect(find.text('Privacy Notice'), findsOneWidget);
      expect(
          find.byKey(const ValueKey('legal-pending-review')), findsOneWidget);
      expect(find.text('Version 2026-11-25 · effective 2026-11-25'),
          findsOneWidget);
      expect(find.text('Section'), findsOneWidget);
      expect(find.textContaining('one item'), findsOneWidget);
    });
  });

  group('re-acceptance after sign-in (app asks; the API does not block)', () {
    Future<(AccountFixture, List<String>)> gate(
        WidgetTester tester, Map<String, Object?> Function(http.Request) answer,
        {int status = 200}) async {
      final events = <String>[];
      final fixture =
          AccountFixture(handler: (r) async => jsonResponse(answer(r), status));
      final controller =
          LegalGateController(LiveLegalRepository(fixture.account));
      await tester.pumpWidget(MaterialApp(
          home: LegalAcceptanceGate(
              controller: controller,
              accountId: accountId,
              onSignOut: () => events.add('signed out'),
              onPrivacy: () => events.add('privacy'),
              child: const Text('the app'))));
      await settleAsync(tester);
      return (fixture, events);
    }

    testWidgets('a current acceptance shows the app', (tester) async {
      await gate(tester, (_) => legalState());
      expect(find.text('the app'), findsOneWidget);
      expect(find.byKey(const ValueKey('legal-acceptance')), findsNothing);
    });

    testWidgets(
        'a newer version is asked for, accepted with the shown versions, then the app opens',
        (tester) async {
      var accepted = false;
      final (fixture, _) = await gate(tester, (r) {
        if (r.method == 'POST' && r.url.path.endsWith('/me/legal')) {
          accepted = true;
        }
        return legalState(required: !accepted, version: '2027-01-01');
      });
      expect(find.byKey(const ValueKey('legal-acceptance')), findsOneWidget);
      expect(
          tester
              .widget<FilledButton>(find.byKey(const ValueKey('legal-accept')))
              .onPressed,
          isNull);
      await tester.tap(find.byKey(const ValueKey('legal-agree')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('legal-accept')));
      await settleAsync(tester);
      final post = fixture.requests.singleWhere(
          (r) => r.method == 'POST' && r.url.path.endsWith('/me/legal'));
      expect(body(post), {
        'accepted': {'terms': '2027-01-01', 'privacy': '2027-01-01'}
      });
      expect(find.text('the app'), findsOneWidget);
    });

    testWidgets(
        'privacy and sign-out stay reachable from the acceptance screen',
        (tester) async {
      final (_, events) = await gate(tester, (_) => legalState(required: true));
      await tester.tap(find.text('Privacy settings and requests'));
      await tester.tap(find.text('Sign out'));
      expect(events, ['privacy', 'signed out']);
    });

    testWidgets('a failed check never locks the person out', (tester) async {
      await gate(tester, (_) => {'detail': 'down'}, status: 503);
      expect(find.text('the app'), findsOneWidget);
    });

    test('privacy, legal and sign-out screens are never gated', () {
      expect(LegalAcceptanceGate.exemptScreens,
          containsAll({84, 88, 90, 91, 92, 93, 94}));
    });
  });

  group('privacy settings (M-084)', () {
    testWidgets(
        'marketing consent can be turned on and off, and sends the shown wording version',
        (tester) async {
      var granted = false;
      final fixture = AccountFixture(handler: (r) async {
        if (r.url.path.endsWith('/me/marketing-consent')) {
          granted = body(r)!['granted'] as bool;
        }
        return jsonResponse(legalState(marketing: granted));
      });
      await tester.pumpWidget(MaterialApp(
          home: LiveSettingsScreen(
              route: const ScreenRoute(84),
              catalog: catalog,
              repository: LiveSettingsRepository(fixture.account),
              account: fixture.account)));
      await settleAsync(tester);
      final switchFinder = find.byKey(const ValueKey('marketing-switch'));
      await tester.ensureVisible(switchFinder);
      expect(tester.widget<SwitchListTile>(switchFinder).value, isFalse);
      await tester.tap(switchFinder);
      await settleAsync(tester);
      final put = fixture.requests.lastWhere((r) => r.method == 'PUT');
      expect(body(put), {'granted': true, 'version': '2026-11-25'});
      expect(tester.widget<SwitchListTile>(switchFinder).value, isTrue);
    });

    testWidgets(
        'the privacy screen still works when the marketing state cannot load',
        (tester) async {
      final fixture = AccountFixture(
          handler: (r) async => r.url.path.endsWith('/me/legal')
              ? jsonResponse({'detail': 'down'}, 503)
              : jsonResponse({}));
      await tester.pumpWidget(MaterialApp(
          home: LiveSettingsScreen(
              route: const ScreenRoute(84),
              catalog: catalog,
              repository: LiveSettingsRepository(fixture.account),
              account: fixture.account)));
      await settleAsync(tester);
      expect(find.text('Delete account request'), findsOneWidget);
      expect(find.byKey(const ValueKey('marketing-switch')), findsNothing);
    });
  });
}
