import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/app/screen_route.dart';
import 'package:kolovibe/features/business/business_context.dart';
import 'package:kolovibe/features/business/business_screens.dart';

import 'support/business_harness.dart';

void main() {
  group('business context (a device-local convenience, never authority)', () {
    test('remembers one business for one account and restores it', () async {
      final store = MemoryBusinessContextStore();
      final context = BusinessContext(store);
      await context.select('account-1', businessId);
      expect(BusinessContext(store).restore('account-1'), completion(businessId));
    });
    test('another account never inherits it', () async {
      final store = MemoryBusinessContextStore();
      await BusinessContext(store).select('account-1', businessId);
      expect(await BusinessContext(store).restore('account-2'), isNull);
    });
    test('a damaged or forged value is the same as no value', () async {
      for (final value in ['not json', '{"account":"account-1"}', '{"account":"account-1","business":"x"}', '[]',
        '{"account":"account-1","business":"$businessId","role":"owner"}']) {
        final store = MemoryBusinessContextStore()..value = value;
        expect(await BusinessContext(store).restore('account-1'), isNull, reason: value);
      }
    });
    test('clearing forgets it on the device and notifies listeners', () async {
      final store = MemoryBusinessContextStore();
      final context = BusinessContext(store);
      await context.select('account-1', businessId);
      var notified = 0;
      context.addListener(() => notified++);
      await context.clear();
      expect(store.value, isNull);
      expect(context.businessId, isNull);
      expect(notified, 1);
    });
    test('refuses an id that is not a business id', () async {
      await expectLater(BusinessContext(MemoryBusinessContextStore()).select('account-1', '../x'), throwsArgumentError);
    });
  });

  group('route space', () {
    test('the 108 designed screens are untouched and the Business screens continue after them', () {
      expect(const ScreenRoute(1).valid, isTrue);
      expect(const ScreenRoute(108).valid, isTrue);
      expect(const ScreenRoute(108).isBusiness, isFalse);
      expect(const ScreenRoute(109).isBusiness, isTrue);
      expect(const ScreenRoute(144).valid, isTrue);
      expect(const ScreenRoute(0).valid, isFalse);
      expect(const ScreenRoute(145).valid, isFalse);
      expect(const ScreenRoute(109).name, '/mobile/M-109');
    });
    test('every Business screen has exactly one distinct number from M-109 to M-144', () {
      const numbers = [
        BusinessScreens.home, BusinessScreens.categories, BusinessScreens.results, BusinessScreens.filters,
        BusinessScreens.detail, BusinessScreens.hours, BusinessScreens.contact, BusinessScreens.reviews,
        BusinessScreens.privacy, BusinessScreens.ask, BusinessScreens.myInquiries, BusinessScreens.conversation,
        BusinessScreens.writeReview, BusinessScreens.myReviews, BusinessScreens.editReview,
        BusinessScreens.withdrawReview, BusinessScreens.report, BusinessScreens.myBusinesses,
        BusinessScreens.register, BusinessScreens.manage, BusinessScreens.editProfile, BusinessScreens.editContacts,
        BusinessScreens.editHours, BusinessScreens.profileStatus, BusinessScreens.verification,
        BusinessScreens.listing, BusinessScreens.inbox, BusinessScreens.inboxThread, BusinessScreens.ownerReviews,
        BusinessScreens.reviewInvitations, BusinessScreens.team, BusinessScreens.redeem, BusinessScreens.switcher,
        BusinessScreens.accessRemoved, BusinessScreens.leave, BusinessScreens.staffHome,
      ];
      expect(numbers.toSet().length, 36);
      expect(numbers.reduce((a, b) => a < b ? a : b), 109);
      expect(numbers.reduce((a, b) => a > b ? a : b), 144);
    });
  });
}
