// Business discovery screens M-109..M-117, over the real parsers and the contract fixtures.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/features/business/business_discovery_screens.dart';
import 'package:kolovibe/features/business/business_ui.dart';

import 'package:flutter/services.dart';
import 'support/audit_harness.dart' show AuditViewport, settleAsync;
import 'support/business_harness.dart';
import 'support/business_screen_harness.dart';

const cafe = '13abeac8-1386-440a-b17c-aeafb48fe96f';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  BusinessHarness gateway(Reply Function(Recorded) answer,
          {bool signedIn = false}) =>
      BusinessHarness(signedIn: signedIn, answer: answer);

  Reply standard(Recorded r) => switch (r.path) {
        '/business-categories' => fx('category_list'),
        '/businesses' => fx('public_search'),
        '/businesses/$cafe' => fx('public_detail_anonymous'),
        '/businesses/$cafe/reviews' => fx('review_list_public'),
        _ => failure(404),
      };

  group('M-109 home', () {
    testWidgets(
        'shows categories and businesses from the service and links onward',
        (tester) async {
      final harness = gateway(standard);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) =>
              BusinessHomeScreen(repository: harness.repository, catalog: c));
      expect(find.text('Food and drink'), findsOneWidget);
      expect(find.text('Fabric and tailoring'), findsOneWidget);
      expect(find.text('Alpha Bakery'), findsOneWidget);
      expect(find.text('Verified'), findsWidgets);
      await bed.tap(tester, 'Food and drink');
      expect(bed.last, 'M-111:category=food');
      await bed.back(tester);
      await bed.tap(tester, 'Alpha Bakery');
      expect(bed.last.startsWith('M-113:'), isTrue);
    });

    testWidgets('a search sends the words to the results screen',
        (tester) async {
      final harness = gateway(standard);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) =>
              BusinessHomeScreen(repository: harness.repository, catalog: c));
      await tester.enterText(find.byType(TextField).first, 'fresh bread');
      await bed.tap(tester, 'Search');
      expect(bed.last, 'M-111:q=fresh+bread');
    });

    testWidgets('one failing section does not hide the rest', (tester) async {
      final harness = gateway(
          (r) => r.path == '/business-categories' ? failure(503) : standard(r));
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) =>
              BusinessHomeScreen(repository: harness.repository, catalog: c));
      expect(find.text('Could not load this'), findsOneWidget);
      expect(find.text('Alpha Bakery'), findsOneWidget);
    });

    testWidgets('empty services say so plainly', (tester) async {
      final harness = gateway((r) => r.path == '/businesses'
          ? fx('public_search', (b) => b['items'] = [])
          : fx('category_list', (b) => b['items'] = []));
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) =>
              BusinessHomeScreen(repository: harness.repository, catalog: c));
      expect(find.text('No categories yet'), findsOneWidget);
      expect(find.text('No businesses yet'), findsOneWidget);
    });

    testWidgets('links to activity, teams and the explainer', (tester) async {
      final harness = gateway(standard);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) =>
              BusinessHomeScreen(repository: harness.repository, catalog: c));
      for (final entry in {
        'My questions to businesses': 'M-119',
        'My reviews': 'M-122',
        'My businesses': 'M-126',
        'Join a business team': 'M-140',
        'What you can see here': 'M-117',
      }.entries) {
        await bed.tap(tester, entry.key);
        expect(bed.last, '${entry.value}:', reason: entry.key);
        await bed.back(tester);
      }
    });
  });

  group('M-110 categories', () {
    testWidgets('lists parents with their children and opens results',
        (tester) async {
      final harness = gateway((r) => fx('category_list', (b) {
            (b['items'] as List).add({
              'active': true,
              'name': 'Bakeries',
              'parent': 'food',
              'slug': 'bakeries'
            });
          }));
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessCategoriesScreen(
              repository: harness.repository, catalog: c));
      expect(find.text('Bakeries'), findsOneWidget);
      await bed.tap(tester, 'Bakeries');
      expect(bed.last, 'M-111:category=bakeries');
      await bed.back(tester);
      await bed.tap(tester, 'All businesses');
      expect(bed.last, 'M-111:');
    });

    testWidgets('offline offers a retry that works', (tester) async {
      var online = false;
      final harness = gateway((r) => online ? fx('category_list') : offline());
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessCategoriesScreen(
              repository: harness.repository, catalog: c));
      expect(find.text('You are offline'), findsOneWidget);
      online = true;
      await bed.tap(tester, 'Try again');
      expect(find.text('Food and drink'), findsOneWidget);
    });
  });

  group('M-111 results', () {
    testWidgets('sends exactly the chosen filters and shows the cards',
        (tester) async {
      final harness = gateway(standard);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessResultsScreen(
              repository: harness.repository,
              catalog: c,
              encodedFilters:
                  'q=bread&category=food&county=montserrado&open=1&verified=1'));
      expect(harness.last.path, '/businesses');
      expect(harness.last.query, {
        'q': 'bread',
        'category': 'food',
        'county': 'montserrado',
        'open_now': 'true',
        'verified': 'true'
      });
      expect(find.text('Alpha Bakery'), findsOneWidget);
      expect(find.text('Filters (4)'), findsOneWidget);
    });

    testWidgets('hand-made route values cannot inject a filter',
        (tester) async {
      final harness = gateway(standard);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessResultsScreen(
              repository: harness.repository,
              catalog: c,
              encodedFilters:
                  'county=atlantis&category=Bad%20Slug&owner=me&verified=yes'));
      expect(harness.last.query, isEmpty);
    });

    testWidgets('empty results offer to clear, and clearing searches again',
        (tester) async {
      final harness = gateway((r) => fx('public_search', (b) {
            if (r.query.isNotEmpty) b['items'] = [];
          }));
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessResultsScreen(
              repository: harness.repository,
              catalog: c,
              encodedFilters: 'q=zzz'));
      expect(find.text('No businesses found'), findsOneWidget);
      await bed.tap(tester, 'Clear search and filters');
      expect(find.text('Alpha Bakery'), findsOneWidget);
      expect(harness.last.query, isEmpty);
    });

    testWidgets('shows more only when the service gives a next page',
        (tester) async {
      var page = 0;
      final harness = gateway((r) {
        if (r.query['cursor'] == 'next-page') {
          page++;
          return fx('public_search', (b) {
            b['items'] = [(b['items'] as List).last];
            b['items'][0]['display_name'] = 'Second Page Shop';
          });
        }
        return fx('public_search', (b) => b['next_cursor'] = 'next-page');
      });
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessResultsScreen(
              repository: harness.repository, catalog: c));
      await bed.tap(tester, 'Show more');
      expect(page, 1);
      expect(find.text('Second Page Shop'), findsOneWidget);
      expect(find.text('Show more'), findsNothing);
    });

    testWidgets(
        'a failure on the next page keeps the first page and offers a retry',
        (tester) async {
      final harness = gateway((r) => r.query.containsKey('cursor')
          ? failure(503)
          : fx('public_search', (b) => b['next_cursor'] = 'next-page'));
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessResultsScreen(
              repository: harness.repository, catalog: c));
      await bed.tap(tester, 'Show more');
      expect(find.text('Could not load more'), findsOneWidget);
      expect(find.text('Alpha Bakery'), findsOneWidget);
    });

    testWidgets('rate limiting is shown as a wait, not an error code',
        (tester) async {
      final harness = gateway((r) => failure(429));
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessResultsScreen(
              repository: harness.repository, catalog: c));
      expect(find.text('Too many attempts'), findsOneWidget);
    });

    testWidgets('hostile business text is shown as plain text', (tester) async {
      const hostile =
          '<script>alert(1)</script> **bold** [link](http://x.test)';
      final harness = gateway((r) => fx('public_search',
          (b) => (b['items'] as List).first['display_name'] = hostile));
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessResultsScreen(
              repository: harness.repository, catalog: c));
      expect(find.text(hostile), findsOneWidget);
    });

    testWidgets('a card never claims closed when hours are unknown',
        (tester) async {
      final harness = gateway(standard);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessResultsScreen(
              repository: harness.repository, catalog: c));
      expect(find.text('Opening hours not published'), findsWidgets);
      expect(find.text('Closed now'), findsNothing);
      expect(find.text('Open now'), findsOneWidget);
    });
  });

  group('M-112 filters', () {
    testWidgets('returns the chosen filters to the results screen',
        (tester) async {
      final harness = gateway(standard);
      final bed = ScreenBed(harness);
      BusinessFilters? chosen;
      await bed.pump(
          tester,
          (c) => Builder(
              builder: (context) => Scaffold(
                  body: TextButton(
                      onPressed: () async => chosen =
                          await Navigator.of(context).push<BusinessFilters>(
                              MaterialPageRoute(
                                  builder: (_) => BusinessFiltersScreen(
                                      repository: harness.repository,
                                      catalog: c,
                                      encodedFilters: 'q=bread'))),
                      child: const Text('open')))));
      await tester.tap(find.text('open'));
      await settleAsync(tester);
      await tester.tap(find.byKey(const ValueKey('filter-verified')));
      await tester.tap(find.byKey(const ValueKey('filter-open')));
      await tester.pumpAndSettle();
      await bed.tap(tester, 'Show results');
      expect(
          chosen,
          const BusinessFilters(
              query: 'bread', openNow: true, verifiedOnly: true));
    });

    testWidgets('reset clears filters but keeps the search words',
        (tester) async {
      final harness = gateway(standard);
      final bed = ScreenBed(harness);
      BusinessFilters? chosen;
      await bed.pump(
          tester,
          (c) => Builder(
              builder: (context) => Scaffold(
                  body: TextButton(
                      onPressed: () async => chosen =
                          await Navigator.of(context).push<BusinessFilters>(
                              MaterialPageRoute(
                                  builder: (_) => BusinessFiltersScreen(
                                      repository: harness.repository,
                                      catalog: c,
                                      encodedFilters:
                                          'q=bread&verified=1&county=lofa'))),
                      child: const Text('open')))));
      await tester.tap(find.text('open'));
      await settleAsync(tester);
      await bed.tap(tester, 'Reset filters');
      await bed.tap(tester, 'Show results');
      expect(chosen, const BusinessFilters(query: 'bread'));
    });
  });

  group('M-113 detail', () {
    testWidgets(
        'shows the business and links to hours, contact, reviews, ask and review',
        (tester) async {
      final harness = gateway(standard);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessDetailScreen(
              repository: harness.repository, catalog: c, businessId: cafe));
      expect(find.text('Fixture Cafe'), findsOneWidget);
      expect(find.text('Verified'), findsOneWidget);
      expect(find.text('No reviews yet'), findsWidgets);
      expect(find.textContaining('+231'), findsNothing,
          reason: 'contact values are only on the contact screen');
      for (final entry in {
        'Opening hours': 'M-114',
        'Contact details': 'M-115',
        'Reviews': 'M-116',
        'Ask a question': 'M-118',
        'Write a review': 'M-121',
      }.entries) {
        await bed.tap(tester, entry.key);
        expect(bed.last, '${entry.value}:$cafe', reason: entry.key);
        await bed.back(tester);
      }
    });

    testWidgets('an unknown or unavailable business is a plain not-found state',
        (tester) async {
      final harness = gateway((r) => failure(404));
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessDetailScreen(
              repository: harness.repository, catalog: c, businessId: cafe));
      expect(find.text('Not found'), findsOneWidget);
      expect(find.text('Ask a question'), findsNothing);
    });

    testWidgets('the rating average appears when the service sends one',
        (tester) async {
      final harness = gateway((r) => fx('public_detail_anonymous',
          (b) => b['rating'] = {'count': 12, 'average': 4.25}));
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessDetailScreen(
              repository: harness.repository, catalog: c, businessId: cafe));
      expect(find.text('4.3 out of 5 · 12 reviews'), findsWidgets);
    });

    testWidgets('the average stays hidden until the service sends one',
        (tester) async {
      final harness = gateway((r) => fx('public_detail_anonymous',
          (b) => b['rating'] = {'count': 12, 'average': null}));
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessDetailScreen(
              repository: harness.repository, catalog: c, businessId: cafe));
      expect(find.text('12 reviews'), findsWidgets);
      expect(find.textContaining('out of 5'), findsNothing);
    });

    testWidgets('an invalid business id never reaches the network',
        (tester) async {
      final harness = gateway(standard);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessDetailScreen(
              repository: harness.repository, catalog: c, businessId: '../me'));
      expect(harness.requests, isEmpty);
      expect(find.text('Something went wrong'), findsOneWidget);
    });

    testWidgets('large text and the small phone do not overflow',
        (tester) async {
      final harness = gateway(standard);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessDetailScreen(
              repository: harness.repository, catalog: c, businessId: cafe),
          viewport: AuditViewportSmall.small,
          textScale: 2);
      expect(tester.takeException(), isNull);
    });
  });

  group('M-114 hours', () {
    testWidgets('lists each weekday and special days', (tester) async {
      final harness = gateway((r) => fx(
          'public_detail_anonymous',
          (b) => b['hours'] = {
                'rules': [
                  {'weekday': 0, 'opens': '08:00', 'closes': '12:00'},
                  {'weekday': 0, 'opens': '14:00', 'closes': '17:00'},
                  {'weekday': 5, 'opens': '09:00', 'closes': '13:00'},
                ],
                'exceptions': [
                  {'on_date': '2026-12-25', 'closed': true},
                  {
                    'on_date': '2026-12-31',
                    'closed': false,
                    'opens': '09:00',
                    'closes': '12:00'
                  },
                ]
              }));
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessHoursScreen(
              repository: harness.repository, catalog: c, businessId: cafe));
      expect(find.text('08:00 – 12:00, 14:00 – 17:00'), findsOneWidget);
      expect(find.text('09:00 – 13:00'), findsOneWidget);
      expect(find.text('Closed'), findsWidgets);
      expect(find.text('2026-12-25'), findsOneWidget);
      expect(find.text('Times are in Africa/Monrovia.'), findsOneWidget);
    });

    testWidgets('no published hours is stated, never shown as closed',
        (tester) async {
      final harness = gateway((r) => fx('public_detail_anonymous', (b) {
            b['hours'] = {'rules': [], 'exceptions': []};
            b['open_now'] = null;
          }));
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessHoursScreen(
              repository: harness.repository, catalog: c, businessId: cafe));
      expect(find.text('Opening hours not published'), findsOneWidget);
      expect(find.text('Monday'), findsNothing);
    });

    testWidgets('reuses the detail just fetched instead of asking again',
        (tester) async {
      final harness = gateway(standard);
      await tester.runAsync(() => harness.repository.detail(cafe));
      final before = harness.requests.length;
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessHoursScreen(
              repository: harness.repository, catalog: c, businessId: cafe));
      expect(harness.requests.length, before);
    });
  });

  group('M-115 contact', () {
    Future<ScreenBed> open(
        WidgetTester tester, Reply Function(Recorded) answer) async {
      final harness = gateway(answer);
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessContactScreen(
              repository: harness.repository, catalog: c, businessId: cafe));
      return bed;
    }

    testWidgets('available contacts are shown and copy only', (tester) async {
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
      await open(tester, (r) => fx('public_detail_signed_in'));
      expect(find.text('+231770000001'), findsOneWidget);
      await tester.tap(find.text('+231770000001'));
      await tester.pump();
      expect(copied, ['+231770000001']);
      expect(find.text('Copied'), findsOneWidget);
    });

    testWidgets('signed out: asks to sign in and returns here', (tester) async {
      final bed = await open(tester, (r) => fx('public_detail_anonymous'));
      expect(find.text('Sign in to see contact details'), findsOneWidget);
      expect(find.textContaining('+231'), findsNothing);
      await bed.tap(tester, 'Sign in');
      expect(bed.pushed.last.screen, 4);
      expect(bed.pushed.last.returnTo, 115);
    });

    testWidgets(
        'verified email required, limit reached and none are each explained',
        (tester) async {
      var bed = await open(
          tester,
          (r) => fx('public_detail_anonymous',
              (b) => b['contacts_access'] = 'verified_email_required'));
      expect(find.text('Verify your email to see contact details'),
          findsOneWidget);
      await bed.tap(tester, 'Open my profile');
      expect(bed.last, 'M-079:');
      bed = await open(
          tester,
          (r) => fx('public_detail_anonymous',
              (b) => b['contacts_access'] = 'limit_reached'));
      expect(find.text('Contact limit reached'), findsOneWidget);
      bed = await open(
          tester,
          (r) => fx('public_detail_anonymous', (b) {
                b['contacts_access'] = 'none';
                b['contacts'] = [];
              }));
      expect(find.text('No public contact details'), findsOneWidget);
    });

    testWidgets(
        'a service answer that discloses contacts without access is refused',
        (tester) async {
      await open(
          tester,
          (r) => fx(
              'public_detail_anonymous',
              (b) => b['contacts'] = [
                    {'kind': 'phone', 'value': '+231000'}
                  ]));
      expect(find.textContaining('+231000'), findsNothing);
      expect(find.text('Something went wrong'), findsOneWidget);
    });
  });

  group('M-116 reviews', () {
    testWidgets(
        'shows reviews, the basis, owner replies, and reports by review id',
        (tester) async {
      final harness = gateway((r) => fx('review_list_public', (b) {
            (b['items'] as List).first['response'] = {
              'body': 'Thank you!',
              'created_at': '2026-11-25T10:00:00Z'
            };
            (b['items'] as List).first['edited_at'] = '2026-11-25T11:00:00Z';
          }));
      final bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessReviewsScreen(
              repository: harness.repository, catalog: c, businessId: cafe));
      expect(find.text('The bread was fresh and the service was friendly.'),
          findsOneWidget);
      expect(find.textContaining('Reviewer 1'), findsOneWidget);
      expect(find.textContaining('Open review'), findsOneWidget);
      expect(find.textContaining('edited'), findsOneWidget);
      expect(find.text('Thank you!'), findsOneWidget);
      await bed.tap(tester, 'Report this review');
      expect(bed.last, 'M-125:review:61604c4b-22e7-4b06-980f-af57ec9cf597');
    });

    testWidgets('no reviews and failure states', (tester) async {
      var harness =
          gateway((r) => fx('review_list_public', (b) => b['items'] = []));
      var bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessReviewsScreen(
              repository: harness.repository, catalog: c, businessId: cafe));
      expect(find.text('No reviews yet'), findsOneWidget);
      harness = gateway((r) => failure(503));
      bed = ScreenBed(harness);
      await bed.pump(
          tester,
          (c) => BusinessReviewsScreen(
              repository: harness.repository, catalog: c, businessId: cafe));
      expect(find.text('Something went wrong'), findsOneWidget);
    });
  });

  group('M-117 explainer', () {
    testWidgets('states what is shown and what is not, with no network call',
        (tester) async {
      final harness = gateway(standard);
      final bed = ScreenBed(harness);
      await bed.pump(tester, (c) => BusinessPrivacyScreen(catalog: c));
      expect(
          find.text('Only what a business chooses to publish'), findsOneWidget);
      expect(find.textContaining('Exact map coordinates are never shown'),
          findsOneWidget);
      expect(harness.requests, isEmpty);
    });
  });

  group('BusinessFilters', () {
    test('round-trips and re-validates', () {
      const filters = BusinessFilters(
          query: 'a b&c=d',
          category: 'food',
          county: 'lofa',
          openNow: true,
          verifiedOnly: true);
      expect(BusinessFilters.decode(filters.encode()), filters);
      expect(const BusinessFilters().encode(), isNull);
      expect(BusinessFilters.decode('%zz').isEmpty, isTrue);
      expect(BusinessFilters.decode('q=${'x' * 101}').query, isNull);
      expect(BusinessFilters.decode('x' * 401).isEmpty, isTrue);
    });
  });
}

/// The audited small phone, named here only so this file does not import the whole audit harness API twice.
class AuditViewportSmall {
  static const small = AuditViewport.small;
}
