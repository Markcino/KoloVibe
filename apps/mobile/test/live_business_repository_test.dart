import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/features/account/live_account_repository.dart';
import 'package:kolovibe/features/business/business_models.dart';
import 'package:kolovibe/features/business/live_business_repository.dart';

import 'support/business_harness.dart';

const key = 'k-0123456789abcdef';
final proofToken = 'p' * 48;
final typed = 'x' * 12;

StepUpProof proofFor(String purpose) => StepUpProof(
    proofToken, purpose, DateTime.now().add(const Duration(minutes: 5)));
const base = '/me/businesses/$businessId';

/// One row per operation the app calls: what must go out, and which real service answer must parse.
class Case {
  Case(this.name, this.method, this.path, this.fixtureName, this.run,
      {this.body, this.query, this.mutating = false, this.signedIn = true});
  final String name;
  final String method;
  final String path;
  final String fixtureName;
  final Future<Object?> Function(LiveBusinessRepository) run;
  final Object? body;
  final Map<String, String>? query;
  final bool mutating;
  final bool signedIn;
}

final cases = <Case>[
  // public reads
  Case('categories', 'GET', '/business-categories', 'category_list',
      (r) => r.categories(),
      signedIn: false),
  Case(
      'search',
      'GET',
      '/businesses',
      'public_search',
      (r) => r.search(
          query: ' bakery ',
          category: 'food',
          county: 'montserrado',
          city: 'Monrovia',
          openNow: true,
          verifiedOnly: true),
      query: {
        'q': 'bakery',
        'category': 'food',
        'county': 'montserrado',
        'city': 'Monrovia',
        'open_now': 'true',
        'verified': 'true'
      },
      signedIn: false),
  Case('detail (anonymous)', 'GET', '/businesses/$businessId',
      'public_detail_anonymous', (r) => r.detail(businessId),
      signedIn: false),
  Case('detail (signed in)', 'GET', '/businesses/$businessId',
      'public_detail_signed_in', (r) => r.detail(businessId)),
  Case('public reviews', 'GET', '/businesses/$businessId/reviews',
      'review_list_public', (r) => r.reviews(businessId),
      signedIn: false),
  // customer
  Case(
      'ask',
      'POST',
      '/businesses/$businessId/inquiries',
      'inquiry_create',
      (r) => r.ask(
          businessId: businessId,
          subject: 'order_question',
          body: '  Do you take large orders?  ',
          key: key),
      body: {
        'subject_code': 'order_question',
        'body': 'Do you take large orders?'
      },
      mutating: true),
  Case('my inquiries', 'GET', '/me/inquiries', 'inquiry_list_mine',
      (r) => r.myInquiries()),
  Case('inquiry', 'GET', '/me/inquiries/$threadId', 'inquiry_get_mine',
      (r) => r.inquiry(threadId)),
  Case(
      'send message',
      'POST',
      '/me/inquiries/$threadId/messages',
      'inquiry_message_customer',
      (r) => r.sendMessage(threadId, 'Any update?', key: key),
      body: {'body': 'Any update?'},
      mutating: true),
  Case('confirm inquiry', 'POST', '/me/inquiries/$threadId/confirm',
      'inquiry_confirm_customer', (r) => r.confirmInquiry(threadId, key: key),
      body: <String, Object?>{}, mutating: true),
  Case('close inquiry', 'POST', '/me/inquiries/$threadId/close',
      'inquiry_close_customer', (r) => r.closeInquiry(threadId, key: key),
      body: <String, Object?>{}, mutating: true),
  Case(
      'write review',
      'POST',
      '/businesses/$businessId/reviews',
      'review_create',
      (r) => r.writeReview(
          businessId: businessId,
          rating: 4,
          title: 'Good',
          body: 'A solid experience overall.',
          invitationCode: 'abcdefghijklmnop0123',
          key: key),
      body: {
        'rating': 4,
        'title': 'Good',
        'body': 'A solid experience overall.',
        'invitation_code': 'abcdefghijklmnop0123'
      },
      mutating: true),
  Case('my reviews', 'GET', '/me/reviews', 'review_list_mine',
      (r) => r.myReviews()),
  Case(
      'edit review',
      'PATCH',
      '/me/reviews/$reviewId',
      'review_edit_mine',
      (r) =>
          r.editReview(reviewId, body: 'Updated review text here.', key: key),
      body: {'body': 'Updated review text here.'},
      mutating: true),
  Case('withdraw review', 'DELETE', '/me/reviews/$reviewId',
      'review_withdraw_mine', (r) => r.withdrawReview(reviewId, key: key),
      mutating: true),
  Case(
      'report',
      'POST',
      '/business-reports',
      'report_create',
      (r) => r.report(
          subjectType: 'review',
          subjectId: reviewId,
          reason: 'misleading',
          details: 'Looks wrong.',
          key: key),
      body: {
        'subject_type': 'review',
        'subject_id': reviewId,
        'reason_code': 'misleading',
        'details': 'Looks wrong.'
      },
      mutating: true),
  // owner and staff
  Case('my businesses', 'GET', '/me/businesses', 'list_mine',
      (r) => r.myBusinesses()),
  Case('business (owner)', 'GET', base, 'get_mine_owner',
      (r) => r.business(businessId)),
  Case('business (staff)', 'GET', base, 'get_mine_staff',
      (r) => r.business(businessId)),
  Case(
      'register',
      'POST',
      '/me/businesses',
      'register',
      (r) => r.register(
          displayName: 'Fixture Bakery',
          legalName: 'Fixture Bakery Ltd',
          key: key),
      body: {
        'display_name': 'Fixture Bakery',
        'legal_name': 'Fixture Bakery Ltd'
      },
      mutating: true),
  Case('profile', 'GET', '$base/profile', 'profile_get',
      (r) => r.profile(businessId)),
  Case('profile (working copy)', 'GET', '$base/profile', 'profile_get_working',
      (r) => r.profile(businessId)),
  Case(
      'edit profile',
      'PATCH',
      '$base/profile',
      'profile_edit',
      (r) => r.editProfile(businessId,
          description: 'Fresh.',
          countyCode: 'montserrado',
          contacts: [const ProfileContact('phone', '+231770000000', true)],
          key: key),
      body: {
        'description': 'Fresh.',
        'county_code': 'montserrado',
        'contacts': [
          {'kind': 'phone', 'value': '+231770000000', 'is_public': true}
        ]
      },
      mutating: true),
  Case('submit profile', 'POST', '$base/profile/submit', 'profile_submit',
      (r) => r.submitProfile(businessId, key: key),
      body: <String, Object?>{}, mutating: true),
  Case(
      'replace hours',
      'PUT',
      '$base/hours',
      'hours_replace',
      (r) => r.replaceHours(businessId, const [HoursRule(0, '08:00', '17:00')],
          const [HoursException('2026-12-25', true, null, null)],
          key: key),
      body: {
        'rules': [
          {'weekday': 0, 'opens': '08:00', 'closes': '17:00'}
        ],
        'exceptions': [
          {'on_date': '2026-12-25', 'closed': true}
        ]
      },
      mutating: true),
  Case('verification status', 'GET', '$base/verification',
      'verification_status_pending', (r) => r.verificationStatus(businessId)),
  Case('verification status (none)', 'GET', '$base/verification',
      'verification_status_none', (r) => r.verificationStatus(businessId)),
  Case(
      'submit verification',
      'POST',
      '$base/verification',
      'verification_submit',
      (r) => r.submitVerification(businessId,
          method: 'manual_review',
          evidence: [(kind: 'registration_number', value: 'LBR-1')],
          key: key),
      body: {
        'method': 'manual_review',
        'declaration': true,
        'evidence': [
          {'kind': 'registration_number', 'value': 'LBR-1'}
        ]
      },
      mutating: true),
  Case(
      'answer for information',
      'POST',
      '$base/verification/evidence',
      'verification_respond',
      (r) => r.respondToVerification(businessId,
          evidence: [(kind: 'note', value: 'More detail.')], key: key),
      body: {
        'evidence': [
          {'kind': 'note', 'value': 'More detail.'}
        ]
      },
      mutating: true),
  Case('listing status', 'GET', '$base/listing', 'listing_status',
      (r) => r.listingStatus(businessId)),
  Case('publish', 'POST', '$base/listing/publish', 'listing_publish',
      (r) => r.publish(businessId, key: key),
      body: <String, Object?>{}, mutating: true),
  Case('unpublish', 'POST', '$base/listing/unpublish', 'listing_unpublish',
      (r) => r.unpublish(businessId, key: key),
      body: <String, Object?>{}, mutating: true),
  Case('inbox', 'GET', '$base/inquiries', 'inquiry_inbox',
      (r) => r.inbox(businessId)),
  Case('inbox thread', 'GET', '$base/inquiries/$threadId', 'inquiry_inbox_get',
      (r) => r.inboxThread(businessId, threadId)),
  Case('reply', 'POST', '$base/inquiries/$threadId/messages', 'inquiry_reply',
      (r) => r.reply(businessId, threadId, 'Yes, we do.', key: key),
      body: {'body': 'Yes, we do.'}, mutating: true),
  Case('close thread', 'POST', '$base/inquiries/$threadId/close',
      'inquiry_inbox_get', (r) => r.closeThread(businessId, threadId, key: key),
      body: <String, Object?>{}, mutating: true),
  Case(
      'confirm thread',
      'POST',
      '$base/inquiries/$threadId/confirm',
      'inquiry_inbox_get',
      (r) => r.confirmThread(businessId, threadId, key: key),
      body: <String, Object?>{},
      mutating: true),
  Case('block customer', 'POST', '$base/inquiries/$threadId/block',
      'inquiry_block', (r) => r.blockCustomer(businessId, threadId, key: key),
      body: <String, Object?>{}, mutating: true),
  Case(
      'respond to review',
      'PUT',
      '$base/reviews/$reviewId/response',
      'review_respond',
      (r) => r.respondToReview(businessId, reviewId, 'Thank you for visiting.',
          key: key),
      body: {'body': 'Thank you for visiting.'},
      mutating: true),
  Case(
      'delete response',
      'DELETE',
      '$base/reviews/$reviewId/response',
      'review_response_delete',
      (r) => r.deleteResponse(businessId, reviewId, key: key),
      mutating: true),
  Case(
      'create review invitation',
      'POST',
      '$base/review-invitations',
      'review_invite_create',
      (r) => r.createReviewInvitation(businessId, key: key),
      body: <String, Object?>{},
      mutating: true),
  Case(
      'revoke review invitation',
      'DELETE',
      '$base/review-invitations/$otherId',
      'review_invite_revoke',
      (r) => r.revokeReviewInvitation(businessId, otherId, key: key),
      mutating: true),
  Case(
      'team', 'GET', '$base/members', 'member_list', (r) => r.team(businessId)),
  Case('invite staff', 'POST', '$base/members/invitations', 'staff_invite',
      (r) => r.inviteStaff(businessId, 'Cashier', key: key),
      body: {'label': 'Cashier'}, mutating: true),
  Case(
      'revoke invitation',
      'DELETE',
      '$base/members/invitations/$otherId',
      'staff_invitation_revoke',
      (r) => r.revokeInvitation(businessId, otherId, key: key),
      mutating: true),
  Case('redeem', 'POST', '/me/business-invitations/redeem', 'staff_redeem',
      (r) => r.redeem('abcdefghijklmnop0123', key: key),
      body: {'code': 'abcdefghijklmnop0123'}, mutating: true),
  Case(
      'remove member',
      'DELETE',
      '$base/members/$otherId',
      'member_remove',
      (r) => r.removeMember(businessId, otherId,
          proof: proofFor('business.member_remove'), key: key),
      mutating: true),
  Case('leave', 'POST', '$base/leave', 'member_leave',
      (r) => r.leave(businessId, key: key),
      body: <String, Object?>{}, mutating: true),
];

void main() {
  for (final c in cases) {
    test(
        '${c.name}: sends exactly the expected request and parses the real service answer',
        () async {
      final harness =
          BusinessHarness(signedIn: c.signedIn, answer: always(c.fixtureName));
      await c.run(harness.repository);
      final sent = harness.last;
      expect([sent.method, sent.path], [c.method, c.path]);
      if (c.query != null) expect(sent.query, c.query);
      if (c.body != null) expect(sent.body, c.body);
      c.mutating
          ? expectKey(sent)
          : expect(sent.headers.containsKey('Idempotency-Key'), isFalse);
      if (c.signedIn) {
        expect(sent.headers['Authorization'], 'Bearer access');
      } else {
        expect(sent.headers.containsKey('Authorization'), isFalse,
            reason: 'a signed-out read must carry no credential');
      }
    });
  }

  test(
      'every request body is built from named fields: no account, owner, role, state or eligibility key can be sent',
      () {
    const forbidden = {
      'account_id',
      'owner_id',
      'role',
      'state',
      'verified',
      'listed',
      'eligible',
      'basis',
      'author_account_id',
      'business_id'
    };
    for (final c in cases.where((c) => c.body is Map)) {
      expect((c.body as Map).keys.toSet().intersection(forbidden), isEmpty,
          reason: c.name);
    }
  });

  test('every operation in the contract is covered', () {
    final contract = (jsonDecode(File('test/fixtures/business/_operations.json')
            .readAsStringSync()) as List)
        .cast<String>()
        .toSet();
    final covered = {
      for (final c in cases)
        '${c.method} ${c.path.replaceAll(RegExp(r'[0-9a-f]{8}-[0-9a-f-]{27}'), '{id}')}'
    };
    expect(contract.difference(covered), isEmpty,
        reason:
            'an operation of the contract has no repository method or no test');
    expect(covered.difference(contract), isEmpty,
        reason: 'the app calls something the contract does not have');
    expect(covered.length, 44);
  });

  group('Decision G step-up', () {
    test(
        'a proof is asked for this business and purpose, and the answer is checked',
        () async {
      final harness = BusinessHarness(
          answer: (_) => (
                status: 200,
                body: {
                  'step_up_token': proofToken,
                  'purpose': 'business.member_remove',
                  'expires_at': DateTime.now()
                      .toUtc()
                      .add(const Duration(minutes: 5))
                      .toIso8601String()
                }
              ));
      final proof = await harness.repository.confirmForBusiness(
          businessId, 'business.member_remove', typed);
      expect([harness.last.method, harness.last.path], ['POST', '/me/step-up']);
      expect(harness.last.body, {
        'current_password': typed,
        'purpose': 'business.member_remove',
        'resource_id': businessId
      });
      expect(harness.last.headers.containsKey('X-Step-Up-Token'), isFalse);
      expect(proof.purpose, 'business.member_remove');
    });

    test('an answer for another purpose or a malformed token is refused',
        () async {
      for (final body in [
        {
          'step_up_token': proofToken,
          'purpose': 'business.close',
          'expires_at': '2999-01-01T00:00:00Z'
        },
        {
          'step_up_token': 'short',
          'purpose': 'business.member_remove',
          'expires_at': '2999-01-01T00:00:00Z'
        },
        {
          'step_up_token': proofToken,
          'purpose': 'business.member_remove',
          'expires_at': '2000-01-01T00:00:00Z'
        },
      ]) {
        final harness =
            BusinessHarness(answer: (_) => (status: 200, body: body));
        await expectLater(
            harness.repository.confirmForBusiness(
                businessId, 'business.member_remove', typed),
            throwsA(anything));
      }
    });

    test(
        'the proof travels in its own header, once, and only on the request it was obtained for',
        () async {
      final harness = BusinessHarness(answer: always('member_remove'));
      final proof = proofFor('business.member_remove');
      await harness.repository
          .removeMember(businessId, otherId, proof: proof, key: key);
      expect(harness.last.headers['X-Step-Up-Token'], proofToken);
      final before = harness.requests.length;
      await expectLater(
          harness.repository
              .removeMember(businessId, otherId, proof: proof, key: key),
          throwsA(isA<ApiFailure>()));
      expect(harness.requests.length, before,
          reason: 'a used proof is never sent again');
      harness.answer = always('member_list');
      await harness.repository.team(businessId);
      expect(harness.last.headers.containsKey('X-Step-Up-Token'), isFalse);
    });

    test('a proof for another purpose cannot remove a member', () async {
      final harness = BusinessHarness(answer: always('member_remove'));
      expect(
          () => harness.repository.removeMember(businessId, otherId,
              proof: proofFor('business.contact_change'), key: key),
          throwsArgumentError);
      expect(harness.requests, isEmpty);
    });
  });
}
