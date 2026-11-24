// Business inbox, replies, invitations and team screens M-135..M-139.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/features/business/business_inbox_screens.dart';
import 'package:kolovibe/features/business/business_models.dart'
    show OneTimeCode;
import 'package:kolovibe/features/business/business_ui.dart';

import 'support/audit_harness.dart' show settleAsync;
import 'support/business_harness.dart';
import 'support/business_screen_harness.dart';

const biz = 'ff74369a-051e-4b9d-ba3f-3f419b1f493f';
const thread = 'b64cc15f-3662-471e-9644-b1ffd4bfd0a6';
const review = '61604c4b-22e7-4b06-980f-af57ec9cf597';

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

  group('M-135 inbox', () {
    testWidgets(
        'lists customers by label only and opens a thread with both ids',
        (tester) async {
      final harness = gateway((r) => fx('inquiry_inbox'));
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessInboxScreen(
              repository: harness.repository, catalog: c, businessId: biz));
      expect(find.textContaining('Customer 1'), findsWidgets);
      expect(find.textContaining('@'), findsNothing);
      await bed.tap(
          tester,
          find.textContaining('Customer 1').evaluate().isNotEmpty
              ? 'Customer 1'
              : 'Customer');
      expect(bed.last.startsWith('M-136:$biz/'), isTrue);
    });

    testWidgets('a blocked conversation is shown as plainly closed',
        (tester) async {
      final harness = gateway((r) => fx('inquiry_inbox',
          (b) => (b['items'] as List).first['state'] = 'blocked'));
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessInboxScreen(
              repository: harness.repository, catalog: c, businessId: biz));
      expect(find.textContaining('Closed'), findsOneWidget);
      expect(find.textContaining('lock'), findsNothing);
    });

    testWidgets('empty, not found and offline states', (tester) async {
      var harness = gateway((r) => fx('inquiry_inbox', (b) => b['items'] = []));
      var bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessInboxScreen(
              repository: harness.repository, catalog: c, businessId: biz));
      expect(find.text('No questions yet'), findsOneWidget);
      harness = gateway((r) => failure(404));
      bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessInboxScreen(
              repository: harness.repository, catalog: c, businessId: biz));
      expect(find.text('Not found'), findsOneWidget);
      harness = gateway((r) => offline());
      bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessInboxScreen(
              repository: harness.repository, catalog: c, businessId: biz));
      expect(find.text('You are offline'), findsOneWidget);
    });
  });

  group('M-136 inbox conversation', () {
    Reply answer(Recorded r, {bool staff = false}) {
      if (r.path == '/me/businesses/$biz') {
        return fx(staff ? 'get_mine_staff' : 'get_mine_owner');
      }
      if (r.method == 'GET') {
        return fx('inquiry_inbox_get', (b) => b['state'] = 'open');
      }
      return switch (r.path.split('/').last) {
        'messages' => fx('inquiry_inbox_get', (b) => b['state'] = 'open'),
        'confirm' => fx('inquiry_confirm_business'),
        'close' => fx('inquiry_close_business'),
        'block' => fx('inquiry_block'),
        _ => failure(404),
      };
    }

    Future<(BusinessHarness, ScreenBed)> open(
        WidgetTester tester, Reply Function(Recorded) a) async {
      final harness = gateway(a);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessInboxThreadScreen(
              repository: harness.repository,
              catalog: c,
              target: const ReviewTarget(biz, thread)));
      return (harness, bed);
    }

    testWidgets('an owner can reply with the exact body and a key',
        (tester) async {
      final (harness, bed) = await open(tester, answer);
      expect(find.text('Do you take large orders?'), findsOneWidget);
      await enter(tester, 0, 'Yes, with two days notice.');
      await press(tester, 'Send reply');
      final sent = harness.requests.firstWhere((r) => r.method == 'POST');
      expect(sent.path, '/me/businesses/$biz/inquiries/$thread/messages');
      expect(sent.body, {'body': 'Yes, with two days notice.'});
      expectKey(sent);
    });

    testWidgets('only an owner sees Block; staff never do', (tester) async {
      await open(tester, answer);
      expect(find.text('Block this customer'), findsOneWidget);
      await open(tester, (r) => answer(r, staff: true));
      expect(find.text('Block this customer'), findsNothing);
      expect(find.text('Close conversation'), findsOneWidget);
      expect(find.text('Send reply'), findsOneWidget);
    });

    testWidgets(
        'blocking asks first, says the customer is not told, then closes the thread',
        (tester) async {
      final (harness, bed) = await open(tester, answer);
      await bed.tap(tester, 'Block this customer');
      expect(find.byKey(const ValueKey('M-106')), findsOneWidget);
      expect(find.textContaining('not told that they were blocked'),
          findsOneWidget);
      expect(harness.requests.where((r) => r.method == 'POST'), isEmpty);
      await tester.tap(find.descendant(
          of: find.byKey(const ValueKey('M-106')),
          matching: find.text('Block customer')));
      await settleAsync(tester);
      expect(harness.last.path, '/me/businesses/$biz/inquiries/$thread/block');
      expect(find.text('This conversation is closed'), findsOneWidget);
      expect(find.text('Send reply'), findsNothing);
      expect(find.text('Do you take large orders?'), findsOneWidget,
          reason: 'messages stay on screen');
    });

    testWidgets('confirm and close keep the messages and cancel sends nothing',
        (tester) async {
      final (harness, bed) = await open(tester, (r) => answer(r));
      await bed.tap(tester, 'Close conversation');
      await tester.tap(find.descendant(
          of: find.byKey(const ValueKey('M-106')),
          matching: find.byType(OutlinedButton)));
      await settleAsync(tester);
      expect(harness.requests.where((r) => r.method == 'POST'), isEmpty);
      await bed.tap(tester, 'Close conversation');
      await tester.tap(find.descendant(
          of: find.byKey(const ValueKey('M-106')),
          matching: find.text('Close conversation')));
      await settleAsync(tester);
      expect(harness.last.path, '/me/businesses/$biz/inquiries/$thread/close');
      expect(find.text('Do you take large orders?'), findsOneWidget);
    });

    testWidgets('a customer message can be reported by id', (tester) async {
      final (_, bed) = await open(tester, answer);
      await bed.tap(tester, 'Report');
      expect(bed.last.startsWith('M-125:inquiry_message:'), isTrue);
    });

    testWidgets('a thread of another business is not found', (tester) async {
      await open(tester, (r) => failure(404));
      expect(find.text('Not found'), findsOneWidget);
    });
  });

  group('M-137 reviews and replies', () {
    Future<(BusinessHarness, ScreenBed)> open(
        WidgetTester tester, Reply Function(Recorded) a) async {
      final harness = gateway(a);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessOwnerReviewsScreen(
              repository: harness.repository, catalog: c, businessId: biz));
      return (harness, bed);
    }

    testWidgets(
        'states plainly that a review cannot be hidden or edited; there is no such control',
        (tester) async {
      await open(tester, (r) => fx('review_list_public'));
      expect(find.text('You can answer, not change, reviews'), findsOneWidget);
      expect(find.text('Hide review'), findsNothing);
      expect(find.text('Edit review'), findsNothing);
      expect(find.text('Delete review'), findsNothing);
    });

    testWidgets('replying sends a PUT with the exact body', (tester) async {
      final (harness, bed) = await open(
          tester,
          (r) => r.method == 'PUT'
              ? fx('review_respond', (b) => b['review_id'] = review)
              : fx('review_list_public'));
      await bed.tap(tester, 'Reply');
      await enter(tester, 0, 'Thank you for visiting.');
      await bed.tap(tester, 'Save reply');
      final sent = harness.requests.firstWhere((r) => r.method == 'PUT');
      expect(sent.path, '/me/businesses/$biz/reviews/$review/response');
      expect(sent.body, {'body': 'Thank you for visiting.'});
      expectKey(sent);
      expect(find.text('Thank you for visiting.'), findsOneWidget);
      expect(find.text('Edit reply'), findsOneWidget);
    });

    testWidgets('removing a reply asks first and then sends DELETE',
        (tester) async {
      final (harness, bed) = await open(
          tester,
          (r) => r.method == 'DELETE'
              ? fx('review_response_delete')
              : fx(
                  'review_list_public',
                  (b) => (b['items'] as List).first['response'] = {
                        'body': 'Thanks!',
                        'created_at': '2026-11-25T10:00:00Z'
                      }));
      expect(find.text('Thanks!'), findsOneWidget);
      await bed.tap(tester, 'Remove reply');
      expect(harness.requests.where((r) => r.method == 'DELETE'), isEmpty);
      await tester.tap(find.descendant(
          of: find.byKey(const ValueKey('M-106')),
          matching: find.text('Remove reply')));
      await settleAsync(tester);
      expect(harness.last.method, 'DELETE');
      expect(find.text('Thanks!'), findsNothing);
    });

    testWidgets('a reply removed by reviewers cannot be changed, and says why',
        (tester) async {
      final (_, bed) = await open(
          tester,
          (r) => r.method == 'PUT'
              ? (status: 409, body: {'detail': 'x', 'code': 'response_removed'})
              : fx('review_list_public'));
      await bed.tap(tester, 'Reply');
      await enter(tester, 0, 'Another reply.');
      await bed.tap(tester, 'Save reply');
      expect(
          find.textContaining('reviewers removed this reply'), findsOneWidget);
    });

    testWidgets('a review can be reported', (tester) async {
      final (_, bed) = await open(tester, (r) => fx('review_list_public'));
      await bed.tap(tester, 'Report review');
      expect(bed.last, 'M-125:review:$review');
    });
  });

  group('M-138 review invitations', () {
    Future<(BusinessHarness, ScreenBed)> open(
        WidgetTester tester, Reply Function(Recorded) a) async {
      final harness = gateway(a);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessReviewInvitationsScreen(
              repository: harness.repository, catalog: c, businessId: biz));
      return (harness, bed);
    }

    testWidgets(
        'the code is shown once, with a warning, and leaves with the screen',
        (tester) async {
      final (harness, bed) =
          await open(tester, (r) => fx('review_invite_create'));
      await bed.tap(tester, 'Make an invitation code');
      expect(find.byKey(const ValueKey('one-time-code')), findsOneWidget);
      expect(find.text('REDACTED-ONE-TIME-CODE'), findsOneWidget);
      expect(find.textContaining('Shown once'), findsOneWidget);
      expect(harness.last.path, '/me/businesses/$biz/review-invitations');
      expectKey(harness.last);
      await bed.tap(tester, 'Done');
      expect(find.text('REDACTED-ONE-TIME-CODE'), findsNothing);
      expect(find.text('Make an invitation code'), findsOneWidget);
    });

    testWidgets(
        'every code request gets a different key, because a replay cannot show the code',
        (tester) async {
      final (harness, bed) =
          await open(tester, (r) => fx('review_invite_create'));
      await bed.tap(tester, 'Make an invitation code');
      await bed.tap(tester, 'Done');
      await bed.tap(tester, 'Make an invitation code');
      final keys =
          harness.requests.map((r) => r.headers['Idempotency-Key']).toSet();
      expect(keys.length, 2);
    });

    testWidgets(
        'revoking sends DELETE for that invitation and removes the code',
        (tester) async {
      final (harness, bed) = await open(
          tester,
          (r) => r.method == 'DELETE'
              ? fx('review_invite_revoke')
              : fx('review_invite_create'));
      await bed.tap(tester, 'Make an invitation code');
      await bed.tap(tester, 'Revoke invitation');
      expect(harness.last.method, 'DELETE');
      expect(harness.last.path,
          '/me/businesses/$biz/review-invitations/edae4b31-0f75-4680-91c3-2cd426e9d7c6');
      expect(find.text('REDACTED-ONE-TIME-CODE'), findsNothing);
    });

    testWidgets('copying puts only the code on the clipboard', (tester) async {
      final copied = <String>[];
      tester.binding.defaultBinaryMessenger
          .setMockMethodCallHandler(SystemChannels.platform, (call) async {
        if (call.method == 'Clipboard.setData') {
          copied.add((call.arguments as Map)['text'] as String);
        }
        return null;
      });
      addTearDown(() => tester.binding.defaultBinaryMessenger
          .setMockMethodCallHandler(SystemChannels.platform, null));
      final (_, bed) = await open(tester, (r) => fx('review_invite_create'));
      await bed.tap(tester, 'Make an invitation code');
      await bed.tap(tester, 'Copy code');
      expect(copied, ['REDACTED-ONE-TIME-CODE']);
    });

    testWidgets('the limit of open invitations is explained', (tester) async {
      final (_, bed) = await open(
          tester,
          (r) =>
              (status: 409, body: {'detail': 'x', 'code': 'invitation_limit'}));
      await bed.tap(tester, 'Make an invitation code');
      expect(find.textContaining('too many open invitations'), findsOneWidget);
    });
  });

  group('M-139 team', () {
    Future<(BusinessHarness, ScreenBed)> open(
        WidgetTester tester, Reply Function(Recorded) a) async {
      final harness = gateway(a);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessTeamScreen(
              repository: harness.repository, catalog: c, businessId: biz));
      return (harness, bed);
    }

    Reply answer(Recorded r) {
      if (r.method == 'GET') return fx('member_list');
      if (r.method == 'DELETE') return fx('staff_invitation_revoke');
      return fx('staff_invite');
    }

    testWidgets(
        'shows people and pending invitations, and has no control to remove a member',
        (tester) async {
      await open(tester, answer);
      expect(find.textContaining('you'), findsWidgets);
      expect(find.text('Cashier'), findsOneWidget);
      expect(find.byKey(const ValueKey('team-removal-unavailable')),
          findsOneWidget);
      expect(find.text('Remove'), findsNothing);
      expect(find.text('Remove member'), findsNothing);
    });

    testWidgets(
        'inviting needs a name, shows the code once and reloads the list',
        (tester) async {
      final (harness, bed) = await open(tester, answer);
      await press(tester, 'Make an invitation code');
      expect(find.textContaining('Give the invitation a name'), findsOneWidget);
      expect(harness.requests.where((r) => r.method == 'POST'), isEmpty);
      await enter(tester, 0, 'Counter');
      await press(tester, 'Make an invitation code');
      final sent = harness.requests.firstWhere((r) => r.method == 'POST');
      expect(sent.path, '/me/businesses/$biz/members/invitations');
      expect(sent.body, {'label': 'Counter'});
      expectKey(sent);
      expect(find.text('REDACTED-ONE-TIME-CODE'), findsOneWidget);
      expect(harness.requests.last.method, 'GET',
          reason: 'the team list is refreshed');
      await bed.tap(tester, 'Done');
      expect(find.text('REDACTED-ONE-TIME-CODE'), findsNothing);
    });

    testWidgets(
        'revoking an invitation asks first and sends DELETE for that id',
        (tester) async {
      final (harness, bed) = await open(tester, answer);
      await bed.tap(tester, 'Cashier');
      expect(harness.requests.where((r) => r.method == 'DELETE'), isEmpty);
      await tester.tap(find.descendant(
          of: find.byKey(const ValueKey('M-106')),
          matching: find.text('Revoke invitation')));
      await settleAsync(tester);
      final sent = harness.requests.firstWhere((r) => r.method == 'DELETE');
      expect(sent.path,
          '/me/businesses/$biz/members/invitations/d35dd3c6-d739-40d3-8359-3999e8bf1ae0');
    });

    testWidgets('the staff limit is explained', (tester) async {
      await open(
          tester,
          (r) => r.method == 'POST'
              ? (status: 409, body: {'detail': 'x', 'code': 'staff_limit'})
              : fx('member_list'));
      await enter(tester, 0, 'Counter');
      await press(tester, 'Make an invitation code');
      expect(find.textContaining('limit of team members'), findsOneWidget);
    });
  });

  test('a one-time code never appears when its holder is printed', () {
    final held = const OneTimeCode<int>(1, 'SECRET-CODE-VALUE-1234');
    expect(held.toString().contains('SECRET'), isFalse);
    expect('$held'.contains('SECRET'), isFalse);
  });
}
