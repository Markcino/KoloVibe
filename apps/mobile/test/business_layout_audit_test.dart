// Every Business screen (M-109..M-144) rendered with real parsers over the contract fixtures, at the two audited iPhone
// sizes and at normal and double text size. A screen that overflows or throws fails. Also proves each is the real page,
// not an error or placeholder.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/app/app_dependencies.dart';
import 'package:kolovibe/app/app_session.dart';
import 'package:kolovibe/app/routes/business_routes.dart';
import 'package:kolovibe/app/routes/route_context.dart';
import 'package:kolovibe/app/screen_route.dart';
import 'package:kolovibe/features/business/business_context.dart';
import 'package:kolovibe/features/business/business_pending_screen.dart';

import 'support/audit_harness.dart';
import 'support/business_harness.dart';
import 'support/business_screen_harness.dart';

const biz = 'ff74369a-051e-4b9d-ba3f-3f419b1f493f';
const thread = 'b64cc15f-3662-471e-9644-b1ffd4bfd0a6';
const review = '61604c4b-22e7-4b06-980f-af57ec9cf597';

Reply answer(Recorded r) {
  final p = r.path;
  if (p == '/business-categories') {
    return fx('category_list');
  }
  if (p == '/businesses') {
    return fx('public_search');
  }
  if (p == '/businesses/$biz') {
    return fx('public_detail_signed_in');
  }
  if (p == '/businesses/$biz/reviews') {
    return fx(
        'review_list_public',
        (b) => (b['items'] as List).first['response'] = {
              'body': 'Thank you for visiting us.',
              'created_at': '2026-11-25T10:00:00Z'
            });
  }
  if (p == '/me/inquiries') {
    return fx('inquiry_list_mine');
  }
  if (p == '/me/inquiries/$thread') {
    return fx('inquiry_get_mine',
        (b) => b['confirmed'] = {'customer': true, 'business': true});
  }
  if (p == '/me/reviews') {
    return fx('review_list_mine');
  }
  if (p == '/me/businesses') {
    return fx('list_mine');
  }
  if (p == '/me/businesses/$biz') {
    return fx('get_mine_owner');
  }
  if (p == '/me/businesses/$biz/profile') {
    return fx('profile_get_working');
  }
  if (p == '/me/businesses/$biz/listing') {
    return fx('listing_status');
  }
  if (p == '/me/businesses/$biz/verification') {
    return fx('verification_status_none');
  }
  if (p == '/me/businesses/$biz/members') {
    return fx('member_list');
  }
  if (p == '/me/businesses/$biz/inquiries') {
    return fx('inquiry_inbox');
  }
  if (p == '/me/businesses/$biz/inquiries/$thread') {
    return fx('inquiry_inbox_get');
  }
  return failure(404);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  /// screen number -> the entity the route carries
  final entities = <int, String?>{
    for (var screen = 109; screen <= 144; screen++) screen: biz,
    109: null,
    110: null,
    111: 'q=bread',
    112: 'q=bread&verified=1',
    117: null,
    119: null,
    120: thread,
    121: '$biz/$thread',
    122: null,
    123: review,
    124: review,
    125: 'review:$review',
    126: null,
    127: null,
    136: '$biz/$thread',
    140: null,
    141: null,
    142: null,
  };

  for (final viewport in [AuditViewport.standard, AuditViewport.small]) {
    for (final scale in [1.0, 2.0]) {
      testWidgets(
          'all 36 Business screens fit at ${viewport.name}, text ${scale}x',
          (tester) async {
        final harness = BusinessHarness(signedIn: true, answer: answer);
        final dependencies = AppDependencies.live(
            'https://api.example.test/api/v1',
            client: harness.client,
            credentialStore: MemoryCredentials(),
            businessContextStore: MemoryBusinessContextStore());
        final bed = ScreenBed(harness);
        final failures = <String>[];
        for (var screen = 109; screen <= 144; screen++) {
          await bed.pump(
              tester,
              (catalog) => Builder(builder: (_) {
                    final built = businessRoute(RouteContext(
                        route: ScreenRoute(screen, entityId: entities[screen]),
                        catalog: catalog,
                        dependencies: dependencies,
                        session: AppSession()));
                    return built ?? const SizedBox();
                  }),
              viewport: viewport,
              textScale: scale);
          final problem = tester.takeException();
          if (problem != null) {
            failures.add('M-$screen: ${problem.toString().split('\n').first}');
          }
          if (find.byType(BusinessPendingScreen).evaluate().isNotEmpty) {
            failures.add('M-$screen: placeholder');
          }
          if (find.text('Something went wrong').evaluate().isNotEmpty) {
            failures.add('M-$screen: error page');
          }
          if (find.text('Not found').evaluate().isNotEmpty) {
            failures.add('M-$screen: not-found page');
          }
        }
        expect(failures, isEmpty);
      });
    }
  }
}
