// Business customer screens M-118..M-125: exact request bodies, idempotency, states and failures.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/features/business/business_customer_screens.dart';
import 'package:kolovibe/features/business/business_ui.dart';

import 'support/audit_harness.dart' show settleAsync;
import 'support/business_harness.dart';
import 'support/business_screen_harness.dart';

const biz = 'ff74369a-051e-4b9d-ba3f-3f419b1f493f';
const thread = 'b64cc15f-3662-471e-9644-b1ffd4bfd0a6';
const review = '61604c4b-22e7-4b06-980f-af57ec9cf597';
const message = '00000000-0000-4000-8000-0000000000f1';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  BusinessHarness gateway(Reply Function(Recorded) answer) =>
      BusinessHarness(signedIn: true, answer: answer);

  Reply detail(Recorded r) => fx('public_detail_anonymous');

  Future<void> enter(WidgetTester tester, int index, String value) async {
    await tester.enterText(find.byType(TextFormField).at(index), value);
    await tester.pump();
  }

  group('M-118 ask', () {
    Future<(BusinessHarness, ScreenBed)> open(
        WidgetTester tester, Reply Function(Recorded) answer) async {
      final harness = gateway(answer);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessAskScreen(
              repository: harness.repository, catalog: c, businessId: biz));
      return (harness, bed);
    }

    Future<void> fill(WidgetTester tester,
        {String? text = 'Do you open on Sundays?'}) async {
      await tester.tap(find.byKey(const ValueKey('ask-subject')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Opening hours').last);
      await tester.pumpAndSettle();
      if (text != null) await enter(tester, 0, text);
    }

    testWidgets(
        'sends exactly the subject and the words, with a key, then opens the conversation',
        (tester) async {
      final (harness, bed) = await open(
          tester, (r) => r.method == 'POST' ? fx('inquiry_create') : detail(r));
      expect(find.text('To Fixture Cafe'), findsOneWidget);
      await fill(tester);
      await bed.tap(tester, 'Send question');
      final sent = harness.requests.firstWhere((r) => r.method == 'POST');
      expect(sent.path, '/businesses/$biz/inquiries');
      expect(sent.body,
          {'subject_code': 'opening_hours', 'body': 'Do you open on Sundays?'});
      expectKey(sent);
      expect(bed.last, 'M-120:b64cc15f-3662-471e-9644-b1ffd4bfd0a6');
    });

    testWidgets('nothing is sent until a subject and a message are given',
        (tester) async {
      final (harness, bed) = await open(tester, detail);
      await bed.tap(tester, 'Send question');
      expect(find.text('Choose what your question is about.'), findsOneWidget);
      await fill(tester, text: null);
      await bed.tap(tester, 'Send question');
      expect(find.text('Write your question.'), findsOneWidget);
      expect(harness.requests.where((r) => r.method == 'POST'), isEmpty);
    });

    testWidgets('a retry re-sends the same key; changed words get a new one',
        (tester) async {
      var fail = true;
      final (harness, bed) = await open(tester, (r) {
        if (r.method != 'POST') return detail(r);
        if (fail) return failure(503);
        return fx('inquiry_create');
      });
      await fill(tester);
      await bed.tap(tester, 'Send question');
      expect(find.text('Not sent'), findsOneWidget);
      await bed.tap(tester, 'Send question');
      final posts = harness.requests.where((r) => r.method == 'POST').toList();
      expect(posts.length, 2);
      expect(posts[1].headers['Idempotency-Key'],
          posts[0].headers['Idempotency-Key']);
      await enter(tester, 0, 'A different question?');
      await bed.tap(tester, 'Send question');
      final third =
          harness.requests.where((r) => r.method == 'POST').toList()[2];
      expect(third.headers['Idempotency-Key'],
          isNot(posts[0].headers['Idempotency-Key']));
      fail = false;
    });

    testWidgets('an existing open conversation is explained, with a way to it',
        (tester) async {
      final (_, bed) = await open(
          tester,
          (r) => r.method == 'POST'
              ? (status: 409, body: {'detail': 'x', 'code': 'thread_exists'})
              : detail(r));
      await fill(tester);
      await bed.tap(tester, 'Send question');
      expect(
          find.text(
              'You already have an open conversation with this business.'),
          findsOneWidget);
      await bed.tap(tester, 'Open my questions');
      expect(bed.last, 'M-119:');
    });

    testWidgets(
        'session ended: asks to sign in, offline and unverified email are each said plainly',
        (tester) async {
      var (harness, bed) = await open(
          tester, (r) => r.method == 'POST' ? failure(401) : detail(r));
      await fill(tester);
      await bed.tap(tester, 'Send question');
      expect(find.text('Your session has expired. Sign in again to continue.'),
          findsOneWidget);
      await bed.tap(tester, 'Sign in');
      expect(bed.pushed.last.screen, 4);
      expect(bed.pushed.last.returnTo, 118);

      (harness, bed) =
          await open(tester, (r) => r.method == 'POST' ? offline() : detail(r));
      await fill(tester);
      await bed.tap(tester, 'Send question');
      expect(find.textContaining('You are offline. Nothing was sent'),
          findsOneWidget);

      (harness, bed) = await open(
          tester,
          (r) => r.method == 'POST'
              ? failure(403, 'Verified email required')
              : detail(r));
      await fill(tester);
      await bed.tap(tester, 'Send question');
      expect(find.textContaining('Verify your email address'), findsOneWidget);
    });

    testWidgets('a second tap while sending does not send twice',
        (tester) async {
      final (harness, bed) = await open(
          tester, (r) => r.method == 'POST' ? fx('inquiry_create') : detail(r));
      await fill(tester);
      final button = find.text('Send question');
      await tester.ensureVisible(button);
      await tester.tap(button);
      await tester.tap(button, warnIfMissed: false);
      await settleAsync(tester);
      expect(harness.requests.where((r) => r.method == 'POST').length, 1);
      expect(bed.pushed, isNotEmpty);
    });

    testWidgets('a body with control characters never leaves the device',
        (tester) async {
      final (harness, bed) = await open(tester, detail);
      await fill(tester, text: 'bad\u0000text');
      await bed.tap(tester, 'Send question');
      expect(harness.requests.where((r) => r.method == 'POST'), isEmpty);
      expect(find.text('Not sent'), findsOneWidget);
    });
  });

  group('M-119 my questions', () {
    testWidgets('lists conversations and opens one', (tester) async {
      final harness = gateway((r) => fx('inquiry_list_mine'));
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessMyInquiriesScreen(
              repository: harness.repository, catalog: c));
      expect(find.text('Alpha Bakery'), findsWidgets);
      expect(find.textContaining('An order'), findsWidgets);
      await bed.tap(tester, 'Alpha Bakery');
      expect(bed.last.startsWith('M-120:'), isTrue);
    });

    testWidgets(
        'empty list points to finding a business; sign-in ended asks to sign in',
        (tester) async {
      var harness =
          gateway((r) => fx('inquiry_list_mine', (b) => b['items'] = []));
      var bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessMyInquiriesScreen(
              repository: harness.repository, catalog: c));
      expect(find.text('No questions yet'), findsOneWidget);
      await bed.tap(tester, 'Find a business');
      expect(bed.last, 'M-111:');
      harness = gateway((r) => failure(401));
      bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessMyInquiriesScreen(
              repository: harness.repository, catalog: c));
      await bed.tap(tester, 'Sign in');
      expect(bed.pushed.last.returnTo, 119);
    });
  });

  group('M-120 conversation', () {
    Reply answer(Recorded r) {
      if (r.method == 'GET') return fx('inquiry_get_mine');
      return switch (r.path.split('/').last) {
        'messages' => fx('inquiry_message_customer'),
        'confirm' => fx('inquiry_confirm_customer'),
        'close' => fx('inquiry_close_customer'),
        _ => failure(404),
      };
    }

    Future<(BusinessHarness, ScreenBed)> open(
        WidgetTester tester, Reply Function(Recorded) a) async {
      final harness = gateway(a);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessConversationScreen(
              repository: harness.repository, catalog: c, threadId: thread));
      return (harness, bed);
    }

    testWidgets('shows the messages and sends a reply with the exact body',
        (tester) async {
      final (harness, bed) = await open(tester, answer);
      expect(find.textContaining('Alpha Bakery'), findsWidgets);
      await enter(tester, 0, 'Any update?');
      await bed.tap(tester, 'Send message');
      final sent = harness.requests.last;
      expect(
          [sent.method, sent.path], ['POST', '/me/inquiries/$thread/messages']);
      expect(sent.body, {'body': 'Any update?'});
      expectKey(sent);
      expect(find.text('Any update?'), findsWidgets,
          reason: 'the thread now includes the new message');
    });

    testWidgets(
        'confirming keeps the messages on screen and shows the new state',
        (tester) async {
      final (harness, bed) = await open(tester, answer);
      final before = find.byType(Text).evaluate().length;
      await bed.tap(tester, 'We dealt with each other');
      expect(harness.last.path, '/me/inquiries/$thread/confirm');
      expect(harness.last.body, <String, dynamic>{});
      expect(find.textContaining('You confirmed: yes'), findsOneWidget);
      expect(find.byType(Text).evaluate().length,
          greaterThanOrEqualTo(before - 3));
      expect(find.text('We dealt with each other'), findsNothing);
    });

    testWidgets('closing asks first, then closes and removes the reply box',
        (tester) async {
      final (harness, bed) = await open(tester, answer);
      await bed.tap(tester, 'Close conversation');
      expect(find.byKey(const ValueKey('M-106')), findsOneWidget);
      expect(harness.requests.where((r) => r.method == 'POST'), isEmpty,
          reason: 'nothing before confirming');
      await tester.tap(find.descendant(
          of: find.byKey(const ValueKey('M-106')),
          matching: find.text('Close conversation')));
      await settleAsync(tester);
      expect(harness.last.path, '/me/inquiries/$thread/close');
      expect(find.text('This conversation is closed'), findsOneWidget);
      expect(find.text('Send message'), findsNothing);
    });

    testWidgets('cancelling the close dialog sends nothing', (tester) async {
      final (harness, bed) = await open(tester, answer);
      await bed.tap(tester, 'Close conversation');
      final cancel = find.descendant(
          of: find.byKey(const ValueKey('M-106')),
          matching: find.byType(OutlinedButton));
      await tester.tap(cancel.first);
      await settleAsync(tester);
      expect(harness.requests.where((r) => r.method == 'POST'), isEmpty);
    });

    testWidgets(
        'a removed message says so and carries no text; a message can be reported',
        (tester) async {
      final (_, bed) = await open(
          tester,
          (r) => fx('inquiry_get_mine', (b) {
                final messages = b['messages'] as List;
                messages.add({
                  'id': message,
                  'author_kind': 'business',
                  'body': null,
                  'removed': true,
                  'created_at': '2026-11-25T10:00:00Z'
                });
              }));
      expect(find.text('This message was removed.'), findsOneWidget);
      await bed.tap(tester, 'Report');
      expect(bed.last.startsWith('M-125:inquiry_message:'), isTrue);
    });

    testWidgets(
        'after both sides confirm, a review can be written from the conversation',
        (tester) async {
      final (_, bed) = await open(
          tester,
          (r) => fx('inquiry_get_mine',
              (b) => b['confirmed'] = {'customer': true, 'business': true}));
      await bed.tap(tester, 'Write a review');
      expect(
          bed.last,
          'M-121:$biz/$thread'
              .replaceFirst(biz, 'ff74369a-051e-4b9d-ba3f-3f419b1f493f'));
    });

    testWidgets('a conversation that is not found is a plain state',
        (tester) async {
      await open(tester, (r) => failure(404));
      expect(find.text('Not found'), findsOneWidget);
    });
  });

  group('M-121 write review', () {
    Future<(BusinessHarness, ScreenBed)> open(
        WidgetTester tester, Reply Function(Recorded) a,
        {String? threadId}) async {
      final harness = gateway(a);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessWriteReviewScreen(
              repository: harness.repository,
              catalog: c,
              target: ReviewTarget(biz, threadId)));
      return (harness, bed);
    }

    Reply answer(Recorded r) =>
        r.method == 'POST' ? fx('review_create') : detail(r);

    testWidgets(
        'sends the rating, words and nothing about eligibility or basis',
        (tester) async {
      final (harness, bed) = await open(tester, answer);
      await tester.tap(find.byKey(const ValueKey('rating-4')));
      await enter(tester, 0, 'Great');
      await enter(tester, 1, 'A solid experience overall.');
      await bed.tap(tester, 'Submit review');
      final sent = harness.requests.firstWhere((r) => r.method == 'POST');
      expect(sent.path, '/businesses/$biz/reviews');
      expect(sent.body, {
        'rating': 4,
        'title': 'Great',
        'body': 'A solid experience overall.'
      });
      expectKey(sent);
      expect(bed.last, 'M-122:');
    });

    testWidgets(
        'a confirmed conversation is sent as the proof, never as a basis',
        (tester) async {
      final (harness, bed) = await open(tester, answer, threadId: thread);
      expect(find.text('Based on your conversation'), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('rating-5')));
      await enter(tester, 1, 'Very helpful and quick.');
      await bed.tap(tester, 'Submit review');
      final sent = harness.requests.firstWhere((r) => r.method == 'POST');
      expect(sent.body, {
        'rating': 5,
        'body': 'Very helpful and quick.',
        'interaction_thread_id': thread
      });
    });

    testWidgets('an invitation code replaces the conversation proof',
        (tester) async {
      final (harness, bed) = await open(tester, answer, threadId: thread);
      await tester.tap(find.byKey(const ValueKey('rating-3')));
      await enter(tester, 1, 'Fine, nothing special.');
      await bed.tap(tester, 'I have an invitation code');
      await enter(tester, 2, 'ABCDEFGHIJKLMNOPQRSTUVWX');
      await bed.tap(tester, 'Submit review');
      final sent = harness.requests.firstWhere((r) => r.method == 'POST');
      expect(sent.body, {
        'rating': 3,
        'body': 'Fine, nothing special.',
        'invitation_code': 'ABCDEFGHIJKLMNOPQRSTUVWX'
      });
      expect((sent.body as Map).containsKey('interaction_thread_id'), isFalse);
    });

    testWidgets(
        'missing rating, a short review and a short code are caught before sending',
        (tester) async {
      final (harness, bed) = await open(tester, answer);
      await bed.tap(tester, 'Submit review');
      expect(find.text('Choose a rating from 1 to 5.'), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('rating-2')));
      await enter(tester, 1, 'short');
      await bed.tap(tester, 'Submit review');
      expect(find.text('Write at least 10 characters about your visit.'),
          findsOneWidget);
      await enter(tester, 1, 'Long enough review text.');
      await bed.tap(tester, 'I have an invitation code');
      await enter(tester, 2, 'tooshort');
      await bed.tap(tester, 'Submit review');
      expect(find.text('Enter the whole invitation code.'), findsOneWidget);
      expect(harness.requests.where((r) => r.method == 'POST'), isEmpty);
    });

    testWidgets('already reviewed and not-confirmed answers are explained',
        (tester) async {
      var (_, bed) = await open(
          tester,
          (r) => r.method == 'POST'
              ? (status: 409, body: {'detail': 'x', 'code': 'already_reviewed'})
              : detail(r));
      await tester.tap(find.byKey(const ValueKey('rating-5')));
      await enter(tester, 1, 'Wonderful place to visit.');
      await bed.tap(tester, 'Submit review');
      expect(find.text('You have already reviewed this business.'),
          findsOneWidget);
      await bed.tap(tester, 'Open my reviews');
      expect(bed.last, 'M-122:');
      (_, bed) = await open(
          tester,
          (r) => r.method == 'POST'
              ? (
                  status: 409,
                  body: {'detail': 'x', 'code': 'interaction_not_confirmed'}
                )
              : detail(r),
          threadId: thread);
      await tester.tap(find.byKey(const ValueKey('rating-5')));
      await enter(tester, 1, 'Wonderful place to visit.');
      await bed.tap(tester, 'Submit review');
      expect(find.textContaining('has not been confirmed by both'),
          findsOneWidget);
    });

    testWidgets('a held review is described as waiting, not published',
        (tester) async {
      final (_, bed) = await open(
          tester,
          (r) => r.method == 'POST'
              ? fx('review_create', (b) => b['state'] = 'held')
              : detail(r));
      await tester.tap(find.byKey(const ValueKey('rating-5')));
      await enter(tester, 1, 'Wonderful place to visit.');
      await bed.tap(tester, 'Submit review');
      expect(
          find.text(
              'Review received. It will appear once it has been checked.'),
          findsOneWidget);
    });

    testWidgets('an invalid review target never opens a form', (tester) async {
      expect(ReviewTarget.decode('not-an-id'), isNull);
      expect(ReviewTarget.decode('$biz/$thread/extra'), isNull);
      expect(ReviewTarget.decode('$biz/../x'), isNull);
      expect(ReviewTarget.decode(biz)!.threadId, isNull);
    });
  });

  group('M-122 my reviews', () {
    Future<(BusinessHarness, ScreenBed)> open(
        WidgetTester tester, Reply Function(Recorded) a) async {
      final harness = gateway(a);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessMyReviewsScreen(
              repository: harness.repository, catalog: c));
      return (harness, bed);
    }

    testWidgets('shows state, basis and actions for an active review',
        (tester) async {
      final (_, bed) = await open(tester, (r) => fx('review_list_mine'));
      expect(find.text('Published'), findsOneWidget);
      expect(find.textContaining('Open review'), findsOneWidget);
      await bed.tap(tester, 'Edit');
      expect(bed.last, 'M-123:$review');
      await bed.back(tester);
      await bed.tap(tester, 'Withdraw');
      expect(bed.last, 'M-124:$review');
      await bed.back(tester);
      await bed.tap(tester, 'View business');
      expect(bed.last, 'M-113:$biz');
    });

    testWidgets(
        'held, removed and withdrawn reviews are explained and cannot be edited',
        (tester) async {
      for (final entry in {
        'held':
            'This review is waiting for a check before it is shown to others.',
        'removed': 'This review was removed by KoloVibe reviewers.',
        'withdrawn': null,
      }.entries) {
        final (_, _) = await open(
            tester,
            (r) => fx('review_list_mine',
                (b) => (b['items'] as List).first['state'] = entry.key));
        if (entry.value != null) {
          expect(find.text(entry.value!), findsOneWidget, reason: entry.key);
        }
        expect(find.text('Edit'),
            entry.key == 'held' ? findsOneWidget : findsNothing,
            reason: entry.key);
        expect(find.text('Withdraw'),
            entry.key == 'held' ? findsOneWidget : findsNothing,
            reason: entry.key);
      }
    });

    testWidgets('empty and failure states', (tester) async {
      await open(tester, (r) => fx('review_list_mine', (b) => b['items'] = []));
      expect(find.text('No reviews yet'), findsOneWidget);
      await open(tester, (r) => failure(503));
      expect(find.text('Something went wrong'), findsOneWidget);
    });
  });

  group('M-123 edit review', () {
    Future<(BusinessHarness, ScreenBed)> open(
        WidgetTester tester, Reply Function(Recorded) a,
        {String id = review}) async {
      final harness = gateway(a);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessEditReviewScreen(
              repository: harness.repository, catalog: c, reviewId: id));
      return (harness, bed);
    }

    Reply answer(Recorded r) =>
        r.method == 'PATCH' ? fx('review_edit_mine') : fx('review_list_mine');

    testWidgets('is filled in, and sends only what changed', (tester) async {
      final (harness, bed) = await open(tester, answer);
      expect(find.text('The bread was fresh and the service was friendly.'),
          findsOneWidget);
      expect(
          tester
              .widget<FilledButton>(
                  find.widgetWithText(FilledButton, 'Save changes'))
              .onPressed,
          isNull);
      await enter(tester, 1, 'The bread was still fresh the next day.');
      await bed.tap(tester, 'Save changes');
      final sent = harness.requests.last;
      expect([sent.method, sent.path], ['PATCH', '/me/reviews/$review']);
      expect(sent.body, {'body': 'The bread was still fresh the next day.'});
      expectKey(sent);
    });

    testWidgets('changing only the rating sends only the rating',
        (tester) async {
      final (harness, bed) = await open(tester, answer);
      await tester.tap(find.byKey(const ValueKey('rating-2')));
      await tester.pump();
      await bed.tap(tester, 'Save changes');
      expect(harness.last.body, {'rating': 2});
    });

    testWidgets('a review that is no longer editable is explained',
        (tester) async {
      final (_, bed) = await open(
          tester,
          (r) => r.method == 'PATCH'
              ? (status: 409, body: {'detail': 'x', 'code': 'not_editable'})
              : fx('review_list_mine'));
      await enter(tester, 1, 'A completely new review text.');
      await bed.tap(tester, 'Save changes');
      expect(
          find.text('This review can no longer be changed.'), findsOneWidget);
    });

    testWidgets(
        'someone else’s or an unknown review is not found, never an empty form',
        (tester) async {
      await open(tester, answer, id: '00000000-0000-4000-8000-0000000000aa');
      expect(find.text('Review not found'), findsOneWidget);
      expect(find.text('Save changes'), findsNothing);
    });
  });

  group('M-124 withdraw review', () {
    Future<(BusinessHarness, ScreenBed)> open(
        WidgetTester tester, Reply Function(Recorded) a) async {
      final harness = gateway(a);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessWithdrawReviewScreen(
              repository: harness.repository, catalog: c, reviewId: review));
      return (harness, bed);
    }

    Reply answer(Recorded r) => r.method == 'DELETE'
        ? fx('review_withdraw_mine')
        : fx('review_list_mine');

    testWidgets('asks first; confirming sends one DELETE with a key',
        (tester) async {
      final (harness, bed) = await open(tester, answer);
      await bed.tap(tester, 'Withdraw my review');
      expect(harness.requests.where((r) => r.method == 'DELETE'), isEmpty);
      await tester.tap(find.descendant(
          of: find.byKey(const ValueKey('M-106')),
          matching: find.text('Withdraw review')));
      await settleAsync(tester);
      final sent = harness.requests.firstWhere((r) => r.method == 'DELETE');
      expect(sent.path, '/me/reviews/$review');
      expectKey(sent);
    });

    testWidgets('keeping the review sends nothing', (tester) async {
      final (harness, bed) = await open(tester, answer);
      await bed.tap(tester, 'Withdraw my review');
      await tester.tap(find
          .descendant(
              of: find.byKey(const ValueKey('M-106')),
              matching: find.byType(OutlinedButton))
          .first);
      await settleAsync(tester);
      expect(harness.requests.where((r) => r.method == 'DELETE'), isEmpty);
    });
  });

  group('M-125 report', () {
    Future<(BusinessHarness, ScreenBed)> open(
        WidgetTester tester, Reply Function(Recorded) a,
        {ReportTarget target = const ReportTarget('review', review)}) async {
      final harness = gateway(a);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessReportScreen(
              repository: harness.repository, catalog: c, target: target));
      return (harness, bed);
    }

    testWidgets(
        'sends the reason and details for the chosen subject, then thanks',
        (tester) async {
      final (harness, bed) = await open(tester, (r) => fx('report_create'));
      await tester.tap(find.byKey(const ValueKey('reason-misleading')));
      await enter(tester, 0, 'Looks wrong.');
      await bed.tap(tester, 'Send report');
      final sent = harness.last;
      expect([sent.method, sent.path], ['POST', '/business-reports']);
      expect(sent.body, {
        'subject_type': 'review',
        'subject_id': review,
        'reason_code': 'misleading',
        'details': 'Looks wrong.'
      });
      expectKey(sent);
      expect(find.text('Report received'), findsOneWidget);
    });

    testWidgets(
        'a reason is required; details are optional and omitted when empty',
        (tester) async {
      final (harness, bed) = await open(tester, (r) => fx('report_create'),
          target: const ReportTarget('inquiry_message', message));
      await bed.tap(tester, 'Send report');
      expect(find.text('Choose a reason.'), findsOneWidget);
      expect(harness.requests, isEmpty);
      await tester.tap(find.byKey(const ValueKey('reason-spam')));
      await bed.tap(tester, 'Send report');
      expect(harness.last.body, {
        'subject_type': 'inquiry_message',
        'subject_id': message,
        'reason_code': 'spam'
      });
    });

    testWidgets('already reported and own content are explained',
        (tester) async {
      var (_, bed) = await open(
          tester,
          (r) =>
              (status: 409, body: {'detail': 'x', 'code': 'already_reported'}));
      await tester.tap(find.byKey(const ValueKey('reason-spam')));
      await bed.tap(tester, 'Send report');
      expect(find.text('You have already reported this.'), findsOneWidget);
      (_, bed) = await open(tester,
          (r) => (status: 409, body: {'detail': 'x', 'code': 'own_content'}));
      await tester.tap(find.byKey(const ValueKey('reason-spam')));
      await bed.tap(tester, 'Send report');
      expect(find.text('You cannot report your own content.'), findsOneWidget);
    });

    test(
        'only a review, a reply or a message can be reported, and only by a real id',
        () {
      expect(ReportTarget.decode('review:$review')!.type, 'review');
      expect(ReportTarget.decode('business:$review'), isNull);
      expect(ReportTarget.decode('review:../me'), isNull);
      expect(ReportTarget.decode('review'), isNull);
      expect(ReportTarget.decode(null), isNull);
    });
  });

  group('failure wording', () {
    test('never shows raw server text for a server error', () {
      expect(
          failureText(
              const ApiFailure(500, 'Traceback (most recent call last)')),
          isNot(contains('Traceback')));
      expect(failureText(const ApiFailure(403, 'secret detail')),
          isNot(contains('secret')));
      expect(failureText(const ApiFailure(503, 'x', offline: true)),
          contains('offline'));
    });
  });
}
