import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/features/business/business_json.dart';
import 'package:kolovibe/features/business/business_models.dart';
import 'package:kolovibe/features/business/live_business_repository.dart';

import 'support/business_harness.dart';

const key = 'k-0123456789abcdef';

Map<String, dynamic> copy(Map<String, dynamic> value) => jsonDecode(jsonEncode(value)) as Map<String, dynamic>;

void main() {
  group('input is validated before any request', () {
    final cases = <String, Future<Object?> Function(LiveBusinessRepository)>{
      'a path id that is not an id': (r) => r.detail('../../admin'),
      'a nested id that is not an id': (r) => r.inboxThread(businessId, 'x'),
      'a subject outside the approved list': (r) => r.ask(businessId: businessId, subject: 'free_text', body: 'Hi', key: key),
      'an empty message': (r) => r.ask(businessId: businessId, subject: 'order_question', body: '   ', key: key),
      'a message over 1,000 characters': (r) => r.sendMessage(threadId, 'a' * 1001, key: key),
      'a control character': (r) => r.sendMessage(threadId, 'bell\x07', key: key),
      'a rating of 0': (r) => r.writeReview(businessId: businessId, rating: 0, body: 'A long enough body.', key: key),
      'a rating of 6': (r) => r.writeReview(businessId: businessId, rating: 6, body: 'A long enough body.', key: key),
      'a review body under 10 characters': (r) => r.writeReview(businessId: businessId, rating: 5, body: 'short', key: key),
      'two proofs at once': (r) => r.writeReview(businessId: businessId, rating: 5, body: 'A long enough body.', interactionThreadId: threadId, invitationCode: 'abcdefghijklmnop0123', key: key),
      'a review edit that changes nothing': (r) => r.editReview(reviewId, key: key),
      'a report subject the service does not accept': (r) => r.report(subjectType: 'business', subjectId: businessId, reason: 'spam', key: key),
      'a report reason outside the list': (r) => r.report(subjectType: 'review', subjectId: reviewId, reason: 'because', key: key),
      'a county outside the list': (r) => r.search(county: 'atlantis'),
      'a category that is not a slug': (r) => r.search(category: 'Food & Drink'),
      'a search over 100 characters': (r) => r.search(query: 'q' * 101),
      'an empty cursor': (r) => r.myInquiries(cursor: ''),
      'a profile edit that changes nothing': (r) => r.editProfile(businessId, key: key),
      'an unknown contact kind': (r) => r.editProfile(businessId, contacts: [const ProfileContact('fax', '123456', true)], key: key),
      'a verification method outside the list': (r) => r.submitVerification(businessId, method: 'selfie', evidence: [(kind: 'note', value: 'ok')], key: key),
      'no evidence': (r) => r.submitVerification(businessId, method: 'manual_review', evidence: const [], key: key),
      'six evidence items': (r) => r.submitVerification(businessId, method: 'manual_review', evidence: [for (var i = 0; i < 6; i++) (kind: 'note', value: 'item $i')], key: key),
      'a short staff code': (r) => r.redeem('short', key: key),
      'a staff label over 40 characters': (r) => r.inviteStaff(businessId, 'x' * 41, key: key),
      'a registration name of one character': (r) => r.register(displayName: 'A', legalName: 'A Ltd', key: key),
    };
    cases.forEach((name, run) {
      test(name, () async {
        final harness = BusinessHarness(answer: always('category_list'));
        await expectLater(run(harness.repository), throwsA(anyOf(isA<FormatException>(), isA<ArgumentError>())));
        expect(harness.requests, isEmpty, reason: 'nothing may be sent');
      });
    });
    test('an idempotency key that is too short is refused by the client', () async {
      final harness = BusinessHarness(answer: always('inquiry_create'));
      await expectLater(harness.repository.ask(businessId: businessId, subject: 'order_question', body: 'Hi', key: 'short'), throwsArgumentError);
      expect(harness.requests, isEmpty);
    });
  });

  group('answers that drift or disclose too much are refused', () {
    Future<Object?> parseDetail(Map<String, dynamic> body) => BusinessHarness(
        answer: (_) => (status: 200, body: body)).repository.detail(businessId);

    test('an extra field in a listing card', () async {
      final body = copy(fixture('public_detail_anonymous').body)..['owner_id'] = businessId;
      await expectLater(parseDetail(body), throwsFormatException);
    });
    test('a missing field', () async {
      final body = copy(fixture('public_detail_anonymous').body)..remove('hours');
      await expectLater(parseDetail(body), throwsFormatException);
    });
    test('contacts that arrive without access being available', () async {
      final body = copy(fixture('public_detail_signed_in').body)..['contacts_access'] = 'sign_in_required';
      await expectLater(parseDetail(body), throwsFormatException);
    });
    test('an unknown access state', () async {
      final body = copy(fixture('public_detail_signed_in').body)..['contacts_access'] = 'granted';
      await expectLater(parseDetail(body), throwsFormatException);
    });
    test('a rating average outside 1 to 5', () async {
      final body = copy(fixture('public_detail_signed_in').body)..['rating'] = {'count': 3, 'average': 9};
      await expectLater(parseDetail(body), throwsFormatException);
    });
    test('a time without an offset', () {
      final body = copy(fixture('inquiry_get_mine').body);
      (body['messages'] as List).first['created_at'] = '2026-11-24T10:00:00';
      expect(() => CustomerInquiry.fromJson(body), throwsFormatException);
    });
    test('a removed message that still carries text', () {
      final body = copy(fixture('inquiry_get_mine').body);
      (body['messages'] as List).first['removed'] = true;
      expect(() => CustomerInquiry.fromJson(body), throwsFormatException);
    });
    test('staff receive no legal name and an owner must', () {
      final staff = copy(fixture('get_mine_staff').body)..['legal_name'] = 'Secret Ltd';
      expect(() => MyBusiness.fromJson(staff), throwsFormatException);
      final owner = copy(fixture('get_mine_owner').body)..remove('legal_name');
      expect(() => MyBusiness.fromJson(owner), throwsFormatException);
      expect(MyBusiness.fromJson(fixture('get_mine_staff').body).legalName, isNull);
      expect(MyBusiness.fromJson(fixture('get_mine_owner').body).isOwner, isTrue);
    });
    test('the customer is only a label to the business', () {
      final body = copy(fixture('inquiry_inbox_get').body)..['customer_id'] = otherId;
      expect(() => BusinessInquiry.fromJson(body), throwsFormatException);
    });
    test('a page with a malformed id is refused whole', () async {
      final body = copy(fixture('public_search').body);
      (body['items'] as List).first['id'] = 'not-an-id';
      await expectLater(BusinessHarness(answer: (_) => (status: 200, body: body)).repository.search(), throwsFormatException);
    });
    test('hours with an exception that is half closed', () {
      expect(() => HoursException.fromJson({'on_date': '2026-12-25', 'closed': true, 'opens': '09:00'}), throwsFormatException);
      expect(() => HoursException.fromJson({'on_date': '2026-12-25', 'closed': false}), throwsFormatException);
      expect(() => HoursRule.fromJson({'weekday': 7, 'opens': '09:00', 'closes': '10:00'}), throwsFormatException);
      expect(() => HoursRule.fromJson({'weekday': 1, 'opens': '9am', 'closes': '10:00'}), throwsFormatException);
    });
  });

  group('failures keep their meaning', () {
    test('the service refusals map to the app failure kinds', () async {
      for (final (status, kind) in [(404, FailureKind.notFound), (403, FailureKind.forbidden), (409, FailureKind.conflict), (429, FailureKind.rateLimited), (401, FailureKind.expired)]) {
        final harness = BusinessHarness(answer: (_) => (status: status, body: {'detail': 'x', 'code': 'invitation_required'}));
        try {
          await harness.repository.business(businessId);
          fail('expected a failure');
        } on ApiFailure catch (failure) {
          expect(failure.kind, kind, reason: '$status');
          expect(failure.code, status == 401 ? isNull : 'invitation_required');
        }
      }
    });
    test('registering without an invitation keeps its stable code', () async {
      final harness = BusinessHarness(answer: always('register_no_invitation'));
      await expectLater(harness.repository.register(displayName: 'No Invite', legalName: 'No Invite Ltd', key: key),
          throwsA(isA<ApiFailure>().having((f) => f.code, 'code', 'invitation_required').having((f) => f.status, 'status', 403)));
    });
  });

  group('public reads and the session', () {
    test('a signed-out reader sends no credential and never calls the session endpoints', () async {
      final harness = BusinessHarness(signedIn: false, answer: always('public_search'));
      await harness.repository.search();
      expect(harness.last.headers.containsKey('Authorization'), isFalse);
    });
    test('an ended session falls back to the anonymous answer instead of failing the page', () async {
      var calls = 0;
      final harness = BusinessHarness(answer: (request) {
        calls++;
        return request.headers.containsKey('Authorization')
            ? (status: 401, body: <String, dynamic>{'detail': 'Sign in again.'})
            : fixture('public_detail_anonymous');
      });
      final detail = await harness.repository.detail(businessId);
      expect(detail.access, ContactAccess.signInRequired);
      expect(detail.contacts, isNull);
      expect(calls, greaterThanOrEqualTo(2));
    });
    test('a protected call with an ended session is a failure, never an anonymous answer', () async {
      final harness = BusinessHarness(answer: (_) => (status: 401, body: <String, dynamic>{'detail': 'x'}));
      await expectLater(harness.repository.myBusinesses(), throwsA(isA<ApiFailure>()));
    });
    test('a signed-out person cannot reach a protected operation', () async {
      final harness = BusinessHarness(signedIn: false, answer: always('list_mine'));
      await expectLater(harness.repository.myBusinesses(), throwsA(isA<ApiFailure>().having((f) => f.status, 'status', 401)));
      expect(harness.requests, isEmpty);
    });
  });

  group('one-time codes', () {
    test('are returned to the caller once and never printed', () async {
      final invite = await BusinessHarness(answer: always('staff_invite')).repository.inviteStaff(businessId, 'Cashier', key: key);
      expect(invite.code, isNotEmpty);
      expect(invite.toString(), isNot(contains(invite.code)));
      final review = await BusinessHarness(answer: always('review_invite_create')).repository.createReviewInvitation(businessId, key: key);
      expect('$review', isNot(contains(review.code)));
    });
    test('the committed fixtures never hold a usable code', () {
      for (final name in ['staff_invite', 'review_invite_create']) {
        expect(fixture(name).body['code'], 'REDACTED-ONE-TIME-CODE');
      }
    });
  });

  test('strict helpers reject the shapes the service must never send', () {
    expect(() => exact({'a': 1, 'b': 2}, 'x', {'a'}), throwsFormatException);
    expect(() => exact({'a': 1}, 'x', {'a', 'b'}), throwsFormatException);
    expect(() => exact([], 'x', {}), throwsFormatException);
    expect(() => whole(true, 'x'), throwsFormatException);
    expect(() => whole(7, 'x', max: 6), throwsFormatException);
    expect(() => moment('2026-11-24', 'x'), throwsFormatException);
    expect(moment('2026-11-24T10:00:00+00:00', 'x').isUtc, isTrue);
    expect(() => listOf(List.filled(3, 1), 'x', (Object? v) => v, max: 2), throwsFormatException);
  });
}
