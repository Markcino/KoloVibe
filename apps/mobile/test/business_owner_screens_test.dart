// Business owner screens M-126..M-134: permissions, exact bodies, locked actions and states.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/features/business/business_context.dart';
import 'package:kolovibe/features/business/business_models.dart';
import 'package:kolovibe/features/business/business_owner_screens.dart';

import 'support/audit_harness.dart' show settleAsync;
import 'support/business_harness.dart';
import 'support/business_screen_harness.dart';

const biz = 'ff74369a-051e-4b9d-ba3f-3f419b1f493f';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  BusinessHarness gateway(Reply Function(Recorded) answer) =>
      BusinessHarness(signedIn: true, answer: answer);

  Future<void> enter(WidgetTester tester, int index, String value) async {
    await tester.enterText(find.byType(TextFormField).at(index), value);
    await tester.pump();
  }

  group('M-126 my businesses', () {
    testWidgets(
        'shows role and state, remembers the choice and opens the right screen',
        (tester) async {
      final harness = gateway((r) => fx('list_mine', (b) {
            (b['items'] as List).add({
              ...Map<String, dynamic>.from((b['items'] as List).first as Map),
              'id': '00000000-0000-4000-8000-0000000000b2',
              'display_name': 'Beta Shop',
              'my_role': 'staff',
              'state': 'under_review',
            }..remove('legal_name'));
          }));
      final bed = ScreenBed(harness);
      final context = BusinessContext(MemoryBusinessContextStore());
      await bed.pump(
          tester,
          (c) => BusinessMyBusinessesScreen(
              repository: harness.repository, catalog: c, context: context));
      expect(find.text('Owner · Verified'), findsOneWidget);
      expect(find.text('Staff · Under review'), findsOneWidget);
      await bed.tap(tester, 'Alpha Bakery');
      expect(bed.last, 'M-128:$biz');
      expect(context.businessId, biz);
      await bed.back(tester);
      await bed.tap(tester, 'Beta Shop');
      expect(bed.last, 'M-144:00000000-0000-4000-8000-0000000000b2');
    });

    testWidgets('empty state and the two entry points', (tester) async {
      final harness = gateway((r) => fx('list_mine', (b) => b['items'] = []));
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessMyBusinessesScreen(
              repository: harness.repository, catalog: c, context: null));
      expect(find.text('No businesses yet'), findsOneWidget);
      await bed.tap(tester, 'Register a business');
      expect(bed.last, 'M-127:');
      await bed.back(tester);
      await bed.tap(tester, 'Join a business team');
      expect(bed.last, 'M-140:');
    });

    testWidgets('an ended session asks to sign in', (tester) async {
      final harness = gateway((r) => failure(401));
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessMyBusinessesScreen(
              repository: harness.repository, catalog: c, context: null));
      await bed.tap(tester, 'Sign in');
      expect(bed.pushed.last.returnTo, 126);
    });
  });

  group('M-127 register', () {
    Future<(BusinessHarness, ScreenBed)> open(
        WidgetTester tester, Reply Function(Recorded) a) async {
      final harness = gateway(a);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessRegisterScreen(
              repository: harness.repository, catalog: c));
      return (harness, bed);
    }

    testWidgets('sends the two names and a key, then opens the new business',
        (tester) async {
      final (harness, bed) = await open(tester, (r) => fx('register'));
      await enter(tester, 0, 'Fixture Bakery');
      await enter(tester, 1, 'Fixture Bakery Ltd');
      await bed.tap(tester, 'Register business');
      expect(harness.last.body, {
        'display_name': 'Fixture Bakery',
        'legal_name': 'Fixture Bakery Ltd'
      });
      expect(harness.last.path, '/me/businesses');
      expectKey(harness.last);
      expect(bed.last, 'M-128:479d3836-798b-4b72-a8a1-183c07549c93');
    });

    testWidgets(
        'without an invitation the screen explains the pilot and offers nothing to retry',
        (tester) async {
      final (_, bed) = await open(tester, (r) => fx('register_no_invitation'));
      await enter(tester, 0, 'No Invite');
      await enter(tester, 1, 'No Invite Ltd');
      await bed.tap(tester, 'Register business');
      expect(find.byKey(const ValueKey('invitation-required')), findsOneWidget);
      expect(find.text('Sign in'), findsNothing);
    });

    testWidgets('the business limit and short names are handled',
        (tester) async {
      final (harness, bed) = await open(
          tester,
          (r) =>
              (status: 409, body: {'detail': 'x', 'code': 'business_limit'}));
      await bed.tap(tester, 'Register business');
      expect(
          find.text(
              'Enter the name customers know and the registered legal name.'),
          findsOneWidget);
      expect(harness.requests, isEmpty);
      await enter(tester, 0, 'Another Shop');
      await enter(tester, 1, 'Another Shop Ltd');
      await bed.tap(tester, 'Register business');
      expect(
          find.text(
              'You have reached the most businesses one account can register.'),
          findsOneWidget);
    });
  });

  group('M-128 manage home', () {
    testWidgets('an owner sees every management row and the listing state',
        (tester) async {
      final harness = gateway((r) => r.path.endsWith('/listing')
          ? fx('listing_status')
          : fx('get_mine_owner'));
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessManageScreen(
              repository: harness.repository, catalog: c, businessId: biz));
      expect(find.text('Alpha Bakery'), findsOneWidget);
      expect(find.text('Listed publicly'), findsOneWidget);
      for (final entry in {
        'Inbox': 'M-135',
        'Opening hours': 'M-131',
        'Business details': 'M-129',
        'Contact details': 'M-130',
        'Profile review': 'M-132',
        'Verification': 'M-133',
        'Listing': 'M-134',
        'Reviews and replies': 'M-137',
        'Review invitations': 'M-138',
        'Team': 'M-139',
      }.entries) {
        await bed.tap(tester, entry.key);
        expect(bed.last, '${entry.value}:$biz', reason: entry.key);
        await bed.back(tester);
      }
      expect(find.text('Leave this business'), findsNothing);
    });

    testWidgets(
        'staff see only their rows, never ask for the listing, and can leave',
        (tester) async {
      final harness = gateway((r) => fx('get_mine_staff'));
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessManageScreen(
              repository: harness.repository, catalog: c, businessId: biz));
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
      expect(find.text('Inbox'), findsOneWidget);
      expect(find.text('Opening hours'), findsOneWidget);
      expect(
          harness.requests.where((r) => r.path.endsWith('/listing')), isEmpty,
          reason: 'the listing is owner information');
      await bed.tap(tester, 'Leave this business');
      expect(bed.last, 'M-143:$biz');
    });

    testWidgets(
        'a business the service will not show is the access-removed state',
        (tester) async {
      final harness = gateway((r) => failure(404));
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessManageScreen(
              repository: harness.repository, catalog: c, businessId: biz));
      expect(find.text('You no longer have access to this business.'),
          findsOneWidget);
      expect(find.text('Inbox'), findsNothing);
    });
  });

  group('M-129 business details', () {
    Future<(BusinessHarness, ScreenBed)> open(
        WidgetTester tester, Reply Function(Recorded) a) async {
      final harness = gateway(a);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessEditProfileScreen(
              repository: harness.repository, catalog: c, businessId: biz));
      return (harness, bed);
    }

    Reply answer(Recorded r) => switch (r.path) {
          '/business-categories' => fx('category_list'),
          '/me/businesses/$biz/profile' =>
            r.method == 'PATCH' ? fx('profile_edit') : fx('profile_get'),
          _ => failure(404),
        };

    testWidgets('is filled in and sends only what changed, never coordinates',
        (tester) async {
      final (harness, bed) = await open(tester, answer);
      expect(find.text('Alpha Bakery'), findsOneWidget);
      expect(
          tester
              .widget<FilledButton>(
                  find.widgetWithText(FilledButton, 'Save draft'))
              .onPressed,
          isNull);
      await enter(tester, 1, 'Fresh bread every morning.');
      await bed.tap(tester, 'Save draft');
      final sent = harness.requests.last;
      expect(
          [sent.method, sent.path], ['PATCH', '/me/businesses/$biz/profile']);
      expect(sent.body, {'description': 'Fresh bread every morning.'});
      expectKey(sent);
      expect(find.byKey(const ValueKey('profile-saved')), findsOneWidget);
      expect(sent.body.toString().contains('latitude'), isFalse);
    });

    testWidgets('a pending review blocks the change with a plain sentence',
        (tester) async {
      final (_, bed) = await open(
          tester,
          (r) => r.method == 'PATCH'
              ? (status: 409, body: {'detail': 'x', 'code': 'revision_pending'})
              : answer(r));
      await enter(tester, 1, 'Changed again.');
      await bed.tap(tester, 'Save draft');
      expect(find.textContaining('already waiting for review'), findsOneWidget);
    });

    testWidgets('a name that is too short is caught before sending',
        (tester) async {
      final (harness, bed) = await open(tester, answer);
      await enter(tester, 0, 'A');
      await bed.tap(tester, 'Save draft');
      expect(find.text('The business name needs at least 2 characters.'),
          findsOneWidget);
      expect(harness.requests.where((r) => r.method == 'PATCH'), isEmpty);
    });
  });

  group('M-130 contact details', () {
    Future<(BusinessHarness, ScreenBed)> open(
        WidgetTester tester, Reply Function(Recorded) a) async {
      final harness = gateway(a);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessEditContactsScreen(
              repository: harness.repository, catalog: c, businessId: biz));
      return (harness, bed);
    }

    testWidgets(
        'on a live profile the editor is not shown: one explanation and the current values',
        (tester) async {
      final (harness, _) = await open(
          tester,
          (r) => fx('profile_get', (b) {
                (b['approved'] as Map)['contacts'] = [
                  {'kind': 'phone', 'value': '+231770000009', 'is_public': true}
                ];
              }));
      expect(find.byKey(const ValueKey('contacts-locked')), findsOneWidget);
      expect(find.text('+231770000009'), findsOneWidget);
      expect(find.text('Add a contact'), findsNothing);
      expect(find.text('Save draft'), findsNothing);
      expect(harness.requests.where((r) => r.method == 'PATCH'), isEmpty);
    });

    testWidgets(
        'before a first approval contacts can be edited and are sent exactly',
        (tester) async {
      final (harness, bed) = await open(
          tester,
          (r) => r.method == 'PATCH'
              ? fx('profile_edit')
              : fx('profile_get_working'));
      expect(find.text('+231770000000'), findsOneWidget);
      await bed.tap(tester, 'Add a contact');
      await tester.pump();
      await enter(tester, 1, '+231770000111');
      await bed.tap(tester, 'Save draft');
      final sent = harness.requests.last;
      expect(sent.method, 'PATCH');
      expect(sent.body, {
        'contacts': [
          {'kind': 'phone', 'value': '+231770000000', 'is_public': true},
          {'kind': 'phone', 'value': '+231770000111', 'is_public': true},
        ]
      });
      expectKey(sent);
      expect(find.byKey(const ValueKey('contacts-saved')), findsOneWidget);
    });

    testWidgets(
        'websites must be https, empty rows are refused, a row can be removed',
        (tester) async {
      final (harness, bed) =
          await open(tester, (r) => fx('profile_get_working'));
      await bed.tap(tester, 'Add a contact');
      await tester.tap(find.byKey(const ValueKey('contact-kind-1')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Website').last);
      await tester.pumpAndSettle();
      await bed.tap(tester, 'Save draft');
      expect(find.text('Fill in or remove every contact row.'), findsOneWidget);
      await enter(tester, 1, 'http://example.test');
      await bed.tap(tester, 'Save draft');
      expect(find.text('Website addresses must start with https://'),
          findsOneWidget);
      await tester
          .ensureVisible(find.byKey(const ValueKey('contact-remove-1')));
      await tester.tap(find.byKey(const ValueKey('contact-remove-1')));
      await tester.pump();
      expect(find.text('Website'), findsNothing);
      expect(harness.requests.where((r) => r.method == 'PATCH'), isEmpty);
    });

    testWidgets(
        'if the service still refuses for step-up, the reason is stated',
        (tester) async {
      final (_, bed) = await open(
          tester,
          (r) => r.method == 'PATCH'
              ? (
                  status: 403,
                  body: {'detail': 'x', 'code': 'step_up_unavailable'}
                )
              : fx('profile_get_working'));
      await bed.tap(tester, 'Save draft');
      expect(
          find.text(
              'This change needs an extra security check that is not available yet.'),
          findsOneWidget);
    });
  });

  group('M-131 opening hours', () {
    Future<(BusinessHarness, ScreenBed)> open(
        WidgetTester tester, Reply Function(Recorded) a) async {
      final harness = gateway(a);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessEditHoursScreen(
              repository: harness.repository, catalog: c, businessId: biz));
      return (harness, bed);
    }

    Reply answer(Recorded r) => r.method == 'PUT'
        ? fx('hours_replace')
        : fx(
            'profile_get',
            (b) => b['hours'] = {
                  'rules': [
                    {'weekday': 0, 'opens': '08:00', 'closes': '17:00'}
                  ],
                  'exceptions': [
                    {'on_date': '2026-12-25', 'closed': true}
                  ]
                });

    testWidgets('loads the current hours and sends the whole replacement set',
        (tester) async {
      final (harness, bed) = await open(tester, answer);
      expect(find.byKey(const ValueKey('open-0-0')), findsOneWidget);
      await bed.tap(tester, 'Add times for Saturday');
      await bed.tap(tester, 'Save opening hours');
      final sent = harness.requests.last;
      expect([sent.method, sent.path], ['PUT', '/me/businesses/$biz/hours']);
      expect(sent.body, {
        'rules': [
          {'weekday': 0, 'opens': '08:00', 'closes': '17:00'},
          {'weekday': 5, 'opens': '08:00', 'closes': '17:00'},
        ],
        'exceptions': [
          {'on_date': '2026-12-25', 'closed': true}
        ],
      });
      expectKey(sent);
    });

    testWidgets(
        'a closing time that is not after opening is caught; so is a bad date',
        (tester) async {
      final (harness, bed) = await open(tester, answer);
      tester
          .widget<DropdownButton<String>>(
              find.byKey(const ValueKey('close-0-0')))
          .onChanged!('07:00');
      await tester.pump();
      await bed.tap(tester, 'Save opening hours');
      expect(find.text('Monday: closing time must be after opening time.'),
          findsOneWidget);
      expect(harness.requests.where((r) => r.method == 'PUT'), isEmpty);
    });

    testWidgets('an impossible special-day date is refused', (tester) async {
      final (harness, bed) = await open(tester, answer);
      await tester.enterText(find.byType(TextFormField).first, '2026-02-30');
      await bed.tap(tester, 'Save opening hours');
      expect(
          find.text(
              'Enter special days as YYYY-MM-DD, for example 2026-12-25.'),
          findsOneWidget);
      expect(harness.requests.where((r) => r.method == 'PUT'), isEmpty);
    });

    testWidgets(
        'saving no times at all is allowed and says what customers will see',
        (tester) async {
      final (harness, bed) = await open(
          tester,
          (r) => r.method == 'PUT'
              ? fx('hours_replace', (b) {
                  b['rules'] = [];
                  b['exceptions'] = [];
                })
              : fx('profile_get'));
      expect(
          find.textContaining('customers are told the hours are not published'),
          findsOneWidget);
      await bed.tap(tester, 'Save opening hours');
      expect(harness.last.body, {'rules': [], 'exceptions': []});
    });
  });

  group('M-132 profile review', () {
    Future<(BusinessHarness, ScreenBed)> open(
        WidgetTester tester, Reply Function(Recorded) a) async {
      final harness = gateway(a);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessProfileStatusScreen(
              repository: harness.repository, catalog: c, businessId: biz));
      return (harness, bed);
    }

    testWidgets('a draft can be submitted; the answer says it will be reviewed',
        (tester) async {
      final (harness, bed) = await open(
          tester,
          (r) => r.method == 'POST'
              ? fx('profile_submit')
              : fx('profile_get_working'));
      expect(find.text('Draft change'), findsOneWidget);
      expect(find.text('No public profile yet'), findsOneWidget);
      await bed.tap(tester, 'Submit for review');
      expect(harness.requests.firstWhere((r) => r.method == 'POST').path,
          '/me/businesses/$biz/profile/submit');
      expectKey(harness.requests.firstWhere((r) => r.method == 'POST'));
      expect(
          find.text(
              'Submitted. KoloVibe reviewers will check it before it goes live.'),
          findsOneWidget);
    });

    testWidgets('a change waiting for review hides the submit button',
        (tester) async {
      await open(
          tester,
          (r) => fx('profile_get_working',
              (b) => (b['working'] as Map)['state'] = 'pending_review'));
      expect(find.text('Waiting for review'), findsOneWidget);
      expect(find.text('Submit for review'), findsNothing);
    });

    testWidgets(
        'the last rejection shows the reviewer reason as the service sent it',
        (tester) async {
      await open(
          tester,
          (r) => fx(
              'profile_get',
              (b) => b['last_rejected'] = {
                    ...Map<String, dynamic>.from(b['approved'] as Map),
                    'state': 'rejected',
                    'reason_code': 'unclear_description',
                  }));
      expect(find.text('Reviewer reason: unclear description'), findsOneWidget);
    });

    testWidgets('incomplete and unchanged answers are explained',
        (tester) async {
      final (_, bed) = await open(
          tester,
          (r) => r.method == 'POST'
              ? (
                  status: 409,
                  body: {'detail': 'x', 'code': 'incomplete_profile'}
                )
              : fx('profile_get_working'));
      await bed.tap(tester, 'Submit for review');
      expect(find.textContaining('The profile is incomplete'), findsOneWidget);
    });
  });

  Future<void> press(WidgetTester tester, String label) async {
    final button = find.widgetWithText(FilledButton, label);
    await tester.ensureVisible(button);
    await tester.pumpAndSettle();
    await tester.tap(button);
    await settleAsync(tester);
  }

  group('M-133 verification', () {
    Future<(BusinessHarness, ScreenBed)> open(
        WidgetTester tester, Reply Function(Recorded) a) async {
      final harness = gateway(a);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessVerificationScreen(
              repository: harness.repository, catalog: c, businessId: biz));
      return (harness, bed);
    }

    testWidgets('submitting needs the declaration and sends text evidence only',
        (tester) async {
      final (harness, bed) = await open(
          tester,
          (r) => r.method == 'POST'
              ? fx('verification_submit')
              : fx('verification_status_none'));
      expect(find.text('Not submitted yet'), findsOneWidget);
      await enter(tester, 0, 'LBR-1');
      await press(tester, 'Send for verification');
      expect(find.text('Confirm the declaration to continue.'), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('verification-declaration')));
      await tester.pump();
      await press(tester, 'Send for verification');
      final sent = harness.requests.firstWhere((r) => r.method == 'POST');
      expect(sent.path, '/me/businesses/$biz/verification');
      expect(sent.body, {
        'method': 'manual_review',
        'declaration': true,
        'evidence': [
          {'kind': 'registration_number', 'value': 'LBR-1'}
        ],
      });
      expectKey(sent);
    });

    testWidgets(
        'a request for information is answered on the evidence route, with no declaration',
        (tester) async {
      final (harness, bed) = await open(
          tester,
          (r) => r.method == 'POST'
              ? fx('verification_status_pending')
              : fx('verification_status_none',
                  (b) => b['state'] = 'needs_info'));
      expect(find.text('Answer the request'), findsOneWidget);
      expect(
          find.byKey(const ValueKey('verification-declaration')), findsNothing);
      await enter(tester, 0, 'Licence 77');
      await press(tester, 'Send answer');
      final sent = harness.requests.firstWhere((r) => r.method == 'POST');
      expect(sent.path, '/me/businesses/$biz/verification/evidence');
      expect(sent.body, {
        'evidence': [
          {'kind': 'registration_number', 'value': 'Licence 77'}
        ]
      });
    });

    testWidgets('waiting and verified states offer no form', (tester) async {
      await open(tester, (r) => fx('verification_status_pending'));
      expect(find.text('Submitted. Waiting for a reviewer.'), findsOneWidget);
      expect(find.text('Send for verification'), findsNothing);
      await open(
          tester,
          (r) =>
              fx('verification_status_none', (b) => b['state'] = 'verified'));
      expect(find.text('Verified'), findsOneWidget);
      expect(find.text('Send for verification'), findsNothing);
    });

    testWidgets('a rejection shows the reason and allows submitting again',
        (tester) async {
      await open(
          tester,
          (r) => fx('verification_status_none', (b) {
                b['state'] = 'rejected';
                b['reason_code'] = 'evidence_unclear';
                b['decided_at'] = '2026-11-25T10:00:00Z';
              }));
      expect(find.textContaining('Reviewer reason: evidence unclear.'),
          findsOneWidget);
      expect(find.text('Send for verification'), findsWidgets);
    });

    testWidgets('evidence rows are required, and at most five', (tester) async {
      final (harness, bed) =
          await open(tester, (r) => fx('verification_status_none'));
      await tester.tap(find.byKey(const ValueKey('verification-declaration')));
      await tester.pump();
      await press(tester, 'Send for verification');
      expect(
          find.text('Fill in or remove every evidence row.'), findsOneWidget);
      for (var i = 0; i < 4; i++) {
        await bed.tap(tester, 'Add another detail');
      }
      expect(find.text('Add another detail'), findsNothing);
      expect(harness.requests.where((r) => r.method == 'POST'), isEmpty);
    });
  });

  group('M-134 listing', () {
    Future<(BusinessHarness, ScreenBed)> open(
        WidgetTester tester, Reply Function(Recorded) a) async {
      final harness = gateway(a);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessListingScreen(
              repository: harness.repository, catalog: c, businessId: biz));
      return (harness, bed);
    }

    testWidgets('an eligible business that is hidden can be shown',
        (tester) async {
      final (harness, bed) = await open(
          tester,
          (r) => r.method == 'POST'
              ? fx('listing_publish')
              : fx('listing_status', (b) {
                  b['listed'] = false;
                  b['owner_wants_listing'] = false;
                }));
      expect(find.text('Not listed'), findsOneWidget);
      await bed.tap(tester, 'Show in search');
      expect(harness.requests.last.path, '/me/businesses/$biz/listing/publish');
      expectKey(harness.last);
      expect(find.text('Listed publicly'), findsOneWidget);
    });

    testWidgets('hiding asks first', (tester) async {
      final (harness, bed) = await open(
          tester,
          (r) => r.method == 'POST'
              ? fx('listing_status', (b) {
                  b['listed'] = false;
                  b['owner_wants_listing'] = false;
                })
              : fx('listing_status'));
      await bed.tap(tester, 'Hide from search');
      expect(find.byKey(const ValueKey('M-106')), findsOneWidget);
      expect(harness.requests.where((r) => r.method == 'POST'), isEmpty);
      await tester.tap(find.descendant(
          of: find.byKey(const ValueKey('M-106')),
          matching: find.text('Hide business')));
      await settleAsync(tester);
      expect(harness.last.path, '/me/businesses/$biz/listing/unpublish');
      expect(find.text('Not listed'), findsOneWidget);
    });

    testWidgets('an ineligible business shows why and offers no publish button',
        (tester) async {
      await open(
          tester,
          (r) => fx('listing_status', (b) {
                b['listed'] = false;
                b['owner_wants_listing'] = false;
                b['eligible'] = false;
                b['reasons'] = ['not_verified', 'no_approved_profile'];
              }));
      expect(find.text('• The business is not verified yet.'), findsOneWidget);
      expect(find.text('• The profile has not been approved yet.'),
          findsOneWidget);
      expect(find.text('Show in search'), findsNothing);
    });
  });

  group('typed answers', () {
    test(
        'a staff business without legal name and an owner without one are both strict',
        () {
      expect(
          MyBusiness.fromJson(fixture('get_mine_staff').body).isOwner, isFalse);
      expect(
          () => MyBusiness.fromJson(
              {...fixture('get_mine_staff').body, 'my_role': 'owner'}),
          throwsFormatException);
      expect(
          () => MyBusiness.fromJson(
              {...fixture('get_mine_owner').body}..remove('legal_name')),
          throwsFormatException);
    });
  });
}
