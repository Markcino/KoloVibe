// Business staff screens M-140..M-144: invitation acceptance, business switching, revoked access and leaving.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/features/business/business_context.dart';
import 'package:kolovibe/features/business/business_owner_screens.dart';
import 'package:kolovibe/features/business/business_screens.dart';
import 'package:kolovibe/features/business/business_staff_screens.dart';

import 'support/audit_harness.dart' show settleAsync;
import 'support/business_harness.dart';
import 'support/business_screen_harness.dart';

const biz = 'ff74369a-051e-4b9d-ba3f-3f419b1f493f';
const other = '00000000-0000-4000-8000-0000000000b2';
const account = '00000000-0000-4000-8000-000000000001';
const code = 'ABCDEFGHIJKLMNOPQRSTUVWX';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  BusinessHarness gateway(Reply Function(Recorded) answer) =>
      BusinessHarness(signedIn: true, answer: answer);

  Future<void> enter(WidgetTester tester, int index, String value) async {
    await tester.enterText(find.byType(TextFormField).at(index), value);
    await tester.pump();
  }

  Future<void> press(WidgetTester tester, String label) async {
    final button = find.widgetWithText(FilledButton, label);
    await tester.ensureVisible(button);
    await tester.pumpAndSettle();
    await tester.tap(button);
    await settleAsync(tester);
  }

  group('M-140 accept an invitation', () {
    Future<(BusinessHarness, ScreenBed, BusinessContext)> open(
        WidgetTester tester, Reply Function(Recorded) a) async {
      final harness = gateway(a);
      final bed = ScreenBed(harness);
      final context = BusinessContext(MemoryBusinessContextStore());
      await bed.pump(
          tester,
          (c) => BusinessRedeemScreen(
              repository: harness.repository, catalog: c, context: context));
      return (harness, bed, context);
    }

    testWidgets(
        'sends only the code and a key, then opens the business as staff',
        (tester) async {
      final (harness, bed, context) =
          await open(tester, (r) => fx('staff_redeem'));
      await enter(tester, 0, code);
      await press(tester, 'Join business');
      final sent = harness.requests.firstWhere((r) => r.method == 'POST');
      expect(sent.path, '/me/business-invitations/redeem');
      expect(sent.body, {'code': code});
      expectKey(sent);
      expect(bed.last, 'M-144:$biz');
      expect(context.businessId, biz,
          reason: 'the choice is remembered for this account');
    });

    testWidgets('the code is hidden while typing', (tester) async {
      await open(tester, (r) => fx('staff_redeem'));
      final field =
          tester.widget<EditableText>(find.byType(EditableText).first);
      expect(field.obscureText, isTrue);
      expect(field.autocorrect, isFalse);
    });

    testWidgets(
        'an unknown, used, revoked or expired code gets the one plain answer',
        (tester) async {
      final (_, _, _) = await open(tester,
          (r) => (status: 404, body: {'detail': 'Invitation unavailable'}));
      await enter(tester, 0, code);
      await press(tester, 'Join business');
      expect(
          find.text(
              'This code did not work. Check it, or ask the business owner for a new one.'),
          findsOneWidget);
    });

    testWidgets(
        'already a member, a full team and a closed business are explained',
        (tester) async {
      for (final entry in {
        'already_member': 'You are already a member of this business.',
        'staff_limit':
            'This business has reached its limit of team members and invitations.',
        'business_closed': 'This business is closed, so it cannot be changed.',
      }.entries) {
        await open(tester,
            (r) => (status: 409, body: {'detail': 'x', 'code': entry.key}));
        await enter(tester, 0, code);
        await press(tester, 'Join business');
        expect(find.text(entry.value), findsOneWidget, reason: entry.key);
      }
    });

    testWidgets(
        'a short code never leaves the device; sign-in expiry offers sign in',
        (tester) async {
      var (harness, bed, _) = await open(tester, (r) => fx('staff_redeem'));
      await enter(tester, 0, 'short');
      await press(tester, 'Join business');
      expect(find.text('Enter the whole code you were given.'), findsOneWidget);
      expect(harness.requests, isEmpty);
      (harness, bed, _) = await open(tester, (r) => failure(401));
      await enter(tester, 0, code);
      await press(tester, 'Join business');
      await bed.tap(tester, 'Sign in');
      expect(bed.pushed.last.returnTo, 140);
    });

    testWidgets('a retry re-sends the same key', (tester) async {
      var fail = true;
      final (harness, _, _) =
          await open(tester, (r) => fail ? failure(503) : fx('staff_redeem'));
      await enter(tester, 0, code);
      await press(tester, 'Join business');
      fail = false;
      await press(tester, 'Join business');
      final posts = harness.requests.where((r) => r.method == 'POST').toList();
      expect(posts.length, 2);
      expect(posts[1].headers['Idempotency-Key'],
          posts[0].headers['Idempotency-Key']);
    });
  });

  group('M-144 staff home and revoked access', () {
    Future<(BusinessHarness, ScreenBed)> open(
        WidgetTester tester, Reply Function(Recorded) a,
        {BusinessContext? context}) async {
      final harness = gateway(a);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessManageScreen(
              repository: harness.repository,
              catalog: c,
              businessId: biz,
              businessContext: context,
              screen: BusinessScreens.staffHome,
              title: 'Your business'));
      return (harness, bed);
    }

    testWidgets('shows only what staff may use, plus switching and leaving',
        (tester) async {
      final (harness, bed) = await open(tester, (r) => fx('get_mine_staff'));
      expect(find.text('Staff'), findsOneWidget);
      for (final shown in [
        'Inbox',
        'Opening hours',
        'Leave this business',
        'Switch business'
      ]) {
        expect(find.text(shown), findsOneWidget, reason: shown);
      }
      for (final hidden in [
        'Business details',
        'Contact details',
        'Profile review',
        'Verification',
        'Listing',
        'Reviews and replies',
        'Review invitations',
        'Team'
      ]) {
        expect(find.text(hidden), findsNothing, reason: hidden);
      }
      expect(harness.requests.length, 1,
          reason: 'one read, and nothing owner-only is asked for');
      await bed.tap(tester, 'Switch business');
      expect(bed.last, 'M-141:');
    });

    testWidgets(
        'when access is gone the business is not shown, the choice is forgotten and another can be chosen',
        (tester) async {
      final context = BusinessContext(MemoryBusinessContextStore());
      await tester.runAsync(() => context.select(account, biz));
      expect(context.businessId, biz);
      final (_, bed) =
          await open(tester, (r) => failure(404), context: context);
      expect(find.text('You no longer have access to this business.'),
          findsOneWidget);
      expect(find.text('Inbox'), findsNothing);
      expect(context.businessId, isNull);
      await bed.tap(tester, 'Choose another business');
      expect(bed.last, 'M-141:');
    });

    testWidgets('a forbidden answer is treated the same as not found',
        (tester) async {
      await open(tester, (r) => failure(403));
      expect(find.text('You no longer have access to this business.'),
          findsOneWidget);
    });

    testWidgets('a service outage is not mistaken for lost access',
        (tester) async {
      await open(tester, (r) => failure(503));
      expect(find.text('You no longer have access to this business.'),
          findsNothing);
      expect(find.text('Something went wrong'), findsOneWidget);
    });
  });

  group('M-141 switch business', () {
    Reply twoBusinesses(Recorded r) => fx('list_mine', (b) {
          (b['items'] as List).add({
            ...Map<String, dynamic>.from((b['items'] as List).first as Map),
            'id': other,
            'display_name': 'Beta Shop',
            'my_role': 'staff',
          }..remove('legal_name'));
        });

    Future<(BusinessHarness, ScreenBed, BusinessContext)> open(
        WidgetTester tester, Reply Function(Recorded) a,
        {String? remembered}) async {
      final harness = gateway(a);
      final bed = ScreenBed(harness);
      final context = BusinessContext(MemoryBusinessContextStore());
      if (remembered != null) {
        await tester.runAsync(() => context.select(account, remembered));
      }
      await bed.pump(
          tester,
          (c) => BusinessSwitcherScreen(
              repository: harness.repository, catalog: c, context: context));
      return (harness, bed, context);
    }

    testWidgets(
        'lists only the businesses the service lists, marks the current one and switches by role',
        (tester) async {
      final (_, bed, context) =
          await open(tester, twoBusinesses, remembered: biz);
      expect(find.text('Alpha Bakery'), findsOneWidget);
      expect(find.text('Beta Shop'), findsOneWidget);
      expect(find.byIcon(Icons.check_circle), findsOneWidget);
      await bed.tap(tester, 'Beta Shop');
      await settleAsync(tester);
      expect(bed.last, 'M-144:$other');
      expect(context.businessId, other);
    });

    testWidgets('an owner business opens the owner home', (tester) async {
      final (_, bed, _) = await open(tester, twoBusinesses);
      await bed.tap(tester, 'Alpha Bakery');
      expect(bed.last, 'M-128:$biz');
    });

    testWidgets(
        'a remembered business that is no longer listed is forgotten and said so',
        (tester) async {
      final (_, _, context) = await open(tester, twoBusinesses,
          remembered: '00000000-0000-4000-8000-0000000000c9');
      expect(find.byKey(const ValueKey('access-lost')), findsOneWidget);
      expect(context.businessId, isNull);
      expect(find.byIcon(Icons.check_circle), findsNothing);
    });

    testWidgets('follows the service’s pages', (tester) async {
      final (harness, _, _) = await open(tester, (r) {
        if (r.query['cursor'] == 'p2') {
          return fx(
              'list_mine',
              (b) =>
                  (b['items'] as List).first['display_name'] = 'Second Page');
        }
        return fx('list_mine', (b) => b['next_cursor'] = 'p2');
      });
      expect(find.text('Alpha Bakery'), findsOneWidget);
      expect(find.text('Second Page'), findsOneWidget);
      expect(harness.requests.length, 2);
    });

    testWidgets('no businesses is a plain state with the two ways in',
        (tester) async {
      final (_, bed, _) =
          await open(tester, (r) => fx('list_mine', (b) => b['items'] = []));
      expect(find.text('No businesses'), findsOneWidget);
      await bed.tap(tester, 'Join a business team');
      expect(bed.last, 'M-140:');
    });
  });

  group('M-142 access removed', () {
    testWidgets('says so plainly and offers only ways out', (tester) async {
      final harness = gateway((r) => failure(500));
      final bed = ScreenBed(harness);
      await bed.pump(tester,
          (c) => BusinessAccessRemovedScreen(catalog: c, context: null));
      expect(find.text('You no longer have access to this business.'),
          findsOneWidget);
      await bed.tap(tester, 'My businesses');
      expect(bed.last, 'M-126:');
      expect(harness.requests, isEmpty);
    });
  });

  group('M-143 leave', () {
    Future<(BusinessHarness, ScreenBed, BusinessContext)> open(
        WidgetTester tester, Reply Function(Recorded) a) async {
      final harness = gateway(a);
      final bed = ScreenBed(harness);
      final context = BusinessContext(MemoryBusinessContextStore());
      await tester.runAsync(() => context.select(account, biz));
      await bed.pump(
          tester,
          (c) => BusinessLeaveScreen(
              repository: harness.repository,
              catalog: c,
              businessId: biz,
              context: context));
      return (harness, bed, context);
    }

    Reply answer(Recorded r) =>
        r.method == 'POST' ? fx('member_leave') : fx('get_mine_staff');

    testWidgets(
        'asks first; confirming sends POST leave with a key and forgets the choice',
        (tester) async {
      final (harness, bed, context) = await open(tester, answer);
      await bed.tap(tester, 'Leave business');
      expect(find.byKey(const ValueKey('M-106')), findsOneWidget);
      expect(harness.requests.where((r) => r.method == 'POST'), isEmpty);
      await tester.tap(find.descendant(
          of: find.byKey(const ValueKey('M-106')),
          matching: find.text('Leave business')));
      await settleAsync(tester);
      final sent = harness.requests.firstWhere((r) => r.method == 'POST');
      expect(sent.path, '/me/businesses/$biz/leave');
      expect(sent.body, <String, dynamic>{});
      expectKey(sent);
      expect(context.businessId, isNull);
      expect(bed.last, 'M-126:');
    });

    testWidgets('cancelling sends nothing and keeps the choice',
        (tester) async {
      final (harness, bed, context) = await open(tester, answer);
      await bed.tap(tester, 'Leave business');
      await tester.tap(find.descendant(
          of: find.byKey(const ValueKey('M-106')),
          matching: find.byType(OutlinedButton)));
      await settleAsync(tester);
      expect(harness.requests.where((r) => r.method == 'POST'), isEmpty);
      expect(context.businessId, biz);
    });

    testWidgets('an owner is told they cannot leave and is offered no button',
        (tester) async {
      await open(tester, (r) => fx('get_mine_owner'));
      expect(find.byKey(const ValueKey('owner-cannot-leave')), findsOneWidget);
      expect(find.byKey(const ValueKey('leave-business')), findsNothing);
    });

    testWidgets(
        'the service refusing an owner leaving is explained, and access lost shows the removed state',
        (tester) async {
      final (_, bed, _) = await open(
          tester,
          (r) => r.method == 'POST'
              ? (status: 409, body: {'detail': 'x', 'code': 'owner_protected'})
              : fx('get_mine_staff'));
      await bed.tap(tester, 'Leave business');
      await tester.tap(find.descendant(
          of: find.byKey(const ValueKey('M-106')),
          matching: find.text('Leave business')));
      await settleAsync(tester);
      expect(find.text('An owner cannot be removed from or leave a business.'),
          findsOneWidget);
      await open(tester, (r) => failure(404));
      expect(find.text('You no longer have access to this business.'),
          findsOneWidget);
    });
  });
}
