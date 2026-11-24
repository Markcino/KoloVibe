import 'dart:math';

import '../../core/network/api_client.dart';
import '../account/live_account_repository.dart';
import 'business_json.dart';
import 'business_lists.dart';
import 'business_models.dart';

/// Every Business operation the app calls, over the one authenticated client.
///
/// No second session or client exists: signed-in calls go through [LiveAccountRepository.authenticatedRequest]
/// (refresh rotation, secure storage and sign-out are unchanged); the four public reads work without a session.
/// The app never sends an account, owner, role, state, verified, listed or eligibility field: who the caller is, what
/// they own and whether a review is eligible are decided by the service from the session. Every request body below
/// is built from named parameters only, so none of those can be added by accident.
class LiveBusinessRepository {
  LiveBusinessRepository(this.api, this.account);
  final ApiClient api;
  final LiveAccountRepository account;

  static final _random = Random.secure();

  /// A fresh idempotency key. A screen takes one per attempt and reuses it on retry, so a repeated tap cannot
  /// apply twice.
  static String newKey() {
    final bytes = List<int>.generate(24, (_) => _random.nextInt(256));
    return bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  }

  static final _slug = RegExp(r'^[a-z0-9-]{2,60}$');
  static final _control = RegExp(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]');

  static String _id(String value) {
    if (!isApiId(value)) throw ArgumentError('Invalid identifier');
    return value;
  }

  static String _clean(String value, String what,
      {int min = 0, int max = 2000, bool multiline = false}) {
    final text = value.trim();
    final bad =
        multiline ? RegExp(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]') : _control;
    if (text.length < min ||
        text.length > max ||
        bad.hasMatch(text) ||
        (!multiline && text.contains('\n'))) {
      throw FormatException('Invalid $what');
    }
    return text;
  }

  static String _code(String value, List<Choice> allowed, String what) {
    if (!allowed.any((c) => c.code == value)) {
      throw FormatException('Invalid $what');
    }
    return value;
  }

  // ---- transport ----------------------------------------------------------------------------------------------

  /// A read that is public but better with a session (contact reveal needs a verified account). A session that has
  /// ended falls back to the anonymous answer instead of failing the page.
  Future<Map<String, dynamic>> _public(String path,
      {Map<String, String>? query}) async {
    // A saved session counts even before the first request of this launch has put an access token in memory.
    if (account.signedInAccountId != null ||
        await account.store.readRefreshToken() != null) {
      try {
        return await account.authenticatedRequest(path, query: query);
      } on ApiFailure catch (failure) {
        if (failure.status != 401) rethrow;
      }
    }
    return api.request(path, query: query);
  }

  Future<Map<String, dynamic>> _send(String path,
          {String method = 'GET',
          Map<String, Object?>? body,
          String? key,
          Map<String, String>? query}) =>
      account.authenticatedRequest(path,
          method: method, body: body, idempotencyKey: key, query: query);

  static Map<String, String>? _page(String? cursor) {
    if (cursor == null) return null;
    if (cursor.isEmpty || cursor.length > 600) {
      throw const FormatException('Invalid cursor');
    }
    return {'cursor': cursor};
  }

  // ---- discovery (public) -------------------------------------------------------------------------------------

  Future<List<BusinessCategory>> categories() async {
    final data =
        exact(await _public('/business-categories'), 'categories', {'items'});
    return listOf(data['items'], 'categories', BusinessCategory.fromJson,
        max: 500);
  }

  Future<ResultPage<BusinessCard>> search(
      {String? query,
      String? category,
      String? county,
      String? city,
      bool openNow = false,
      bool verifiedOnly = false,
      String? cursor}) async {
    final params = <String, String>{};
    if (query != null && query.trim().isNotEmpty) {
      params['q'] = _clean(query, 'search', min: 1, max: 100);
    }
    if (category != null) {
      if (!_slug.hasMatch(category)) {
        throw const FormatException('Invalid category');
      }
      params['category'] = category;
    }
    if (county != null) params['county'] = _code(county, counties, 'county');
    if (city != null && city.trim().isNotEmpty) {
      params['city'] = _clean(city, 'city', min: 1, max: 80);
    }
    if (openNow) params['open_now'] = 'true';
    if (verifiedOnly) params['verified'] = 'true';
    if (cursor != null) params.addAll(_page(cursor)!);
    return ResultPage.parse(
        await _public('/businesses', query: params.isEmpty ? null : params),
        'businesses',
        BusinessCard.fromJson);
  }

  final Map<String, ({DateTime at, BusinessDetail value})> _details = {};

  /// Always asks the service, and remembers the answer for [detailCached].
  Future<BusinessDetail> detail(String businessId) async {
    final value = BusinessDetail.fromJson(
        await _public('/businesses/${_id(businessId)}'));
    if (_details.length > 20) _details.clear();
    _details['${account.signedInAccountId ?? 'anonymous'}:$businessId'] =
        (at: DateTime.now(), value: value);
    return value;
  }

  /// The hours and contact screens open straight after the detail screen. Reading contact details is limited per
  /// person, so they reuse the answer fetched a moment ago (for the same signed-in account only) instead of asking
  /// again and using up more of that limit.
  Future<BusinessDetail> detailCached(String businessId,
      {Duration maxAge = const Duration(minutes: 1)}) async {
    final held =
        _details['${account.signedInAccountId ?? 'anonymous'}:$businessId'];
    if (held != null && DateTime.now().difference(held.at) < maxAge) {
      return held.value;
    }
    return detail(businessId);
  }

  Future<ResultPage<PublicReview>> reviews(String businessId,
          {String? cursor}) async =>
      ResultPage.parse(
          await _public('/businesses/${_id(businessId)}/reviews',
              query: _page(cursor)),
          'reviews',
          PublicReview.fromJson);

  // ---- customer -----------------------------------------------------------------------------------------------

  Future<CustomerInquiry> ask(
          {required String businessId,
          required String subject,
          required String body,
          required String key}) async =>
      CustomerInquiry.fromJson(await _send(
          '/businesses/${_id(businessId)}/inquiries',
          method: 'POST',
          key: key,
          body: {
            'subject_code': _code(subject, inquirySubjects, 'subject'),
            'body': _clean(body, 'message', min: 1, max: 1000, multiline: true),
          }));

  Future<ResultPage<CustomerInquiry>> myInquiries({String? cursor}) async =>
      ResultPage.parse(await _send('/me/inquiries', query: _page(cursor)),
          'inquiries', CustomerInquiry.fromJson);

  Future<CustomerInquiry> inquiry(String threadId) async =>
      CustomerInquiry.fromJson(await _send('/me/inquiries/${_id(threadId)}'));

  Future<CustomerInquiry> sendMessage(String threadId, String body,
          {required String key}) async =>
      CustomerInquiry.fromJson(await _send(
          '/me/inquiries/${_id(threadId)}/messages',
          method: 'POST',
          key: key,
          body: {
            'body': _clean(body, 'message', min: 1, max: 1000, multiline: true)
          }));

  Future<CustomerInquiry> closeInquiry(String threadId,
          {required String key}) async =>
      CustomerInquiry.fromJson(await _send(
          '/me/inquiries/${_id(threadId)}/close',
          method: 'POST',
          key: key,
          body: const {}));

  Future<CustomerInquiry> confirmInquiry(String threadId,
          {required String key}) async =>
      CustomerInquiry.fromJson(await _send(
          '/me/inquiries/${_id(threadId)}/confirm',
          method: 'POST',
          key: key,
          body: const {}));

  /// Eligibility is decided by the service. [interactionThreadId] or [invitationCode] are only the proof the
  /// customer holds; the service validates it and derives the basis. Both together are refused before sending.
  Future<OwnReview> writeReview(
      {required String businessId,
      required int rating,
      String? title,
      required String body,
      String? interactionThreadId,
      String? invitationCode,
      required String key}) async {
    if (rating < 1 || rating > 5) throw const FormatException('Invalid rating');
    if (interactionThreadId != null && invitationCode != null) {
      throw const FormatException('Use one proof');
    }
    final heading = title == null || title.trim().isEmpty
        ? null
        : _clean(title, 'title', max: 100);
    return OwnReview.fromJson(await _send(
        '/businesses/${_id(businessId)}/reviews',
        method: 'POST',
        key: key,
        body: {
          'rating': rating,
          if (heading != null) 'title': heading,
          'body': _clean(body, 'review', min: 10, max: 2000, multiline: true),
          if (interactionThreadId != null)
            'interaction_thread_id': _id(interactionThreadId),
          if (invitationCode != null)
            'invitation_code': _clean(invitationCode, 'code', min: 16, max: 64),
        }));
  }

  final Map<String, OwnReview> _ownReviews = {};
  String _mine(String reviewId) => '${account.signedInAccountId}:$reviewId';

  Future<ResultPage<OwnReview>> myReviews({String? cursor}) async {
    final page = ResultPage.parse(
        await _send('/me/reviews', query: _page(cursor)),
        'reviews',
        OwnReview.fromJson);
    for (final review in page.items) {
      _ownReviews[_mine(review.id)] = review;
    }
    return page;
  }

  /// The service has no "read one of my reviews" operation, so the edit and withdraw screens find it in the list
  /// (remembered from the list screen, else by paging through it).
  Future<OwnReview?> findOwnReview(String reviewId) async {
    _id(reviewId);
    final held = _ownReviews[_mine(reviewId)];
    if (held != null) return held;
    String? cursor;
    for (var page = 0; page < 10; page++) {
      final result = await myReviews(cursor: cursor);
      final found = _ownReviews[_mine(reviewId)];
      if (found != null) return found;
      cursor = result.nextCursor;
      if (cursor == null) break;
    }
    return null;
  }

  Future<OwnReview> editReview(String reviewId,
      {int? rating, String? title, String? body, required String key}) async {
    if (rating != null && (rating < 1 || rating > 5)) {
      throw const FormatException('Invalid rating');
    }
    final changes = <String, Object?>{
      if (rating != null) 'rating': rating,
      if (title != null) 'title': _clean(title, 'title', max: 100),
      if (body != null)
        'body': _clean(body, 'review', min: 10, max: 2000, multiline: true),
    };
    if (changes.isEmpty) throw const FormatException('Nothing to change');
    final updated = OwnReview.fromJson(await _send(
        '/me/reviews/${_id(reviewId)}',
        method: 'PATCH',
        key: key,
        body: changes));
    _ownReviews[_mine(updated.id)] = updated;
    return updated;
  }

  Future<OwnReview> withdrawReview(String reviewId,
      {required String key}) async {
    final updated = OwnReview.fromJson(await _send(
        '/me/reviews/${_id(reviewId)}',
        method: 'DELETE',
        key: key));
    _ownReviews[_mine(updated.id)] = updated;
    return updated;
  }

  /// Only a review, an owner response or an inquiry message can be reported; the service has no report on a
  /// business listing.
  Future<ReportReceipt> report(
      {required String subjectType,
      required String subjectId,
      required String reason,
      String? details,
      required String key}) async {
    if (!const {'review', 'review_response', 'inquiry_message'}
        .contains(subjectType)) {
      throw const FormatException('Invalid subject');
    }
    final extra = details == null || details.trim().isEmpty
        ? null
        : _clean(details, 'details', max: 1000, multiline: true);
    return ReportReceipt.fromJson(
        await _send('/business-reports', method: 'POST', key: key, body: {
      'subject_type': subjectType,
      'subject_id': _id(subjectId),
      'reason_code': _code(reason, reportReasons, 'reason'),
      if (extra != null) 'details': extra,
    }));
  }

  // ---- owner and staff: businesses --------------------------------------------------------------------------------

  Future<ResultPage<MyBusiness>> myBusinesses({String? cursor}) async =>
      ResultPage.parse(await _send('/me/businesses', query: _page(cursor)),
          'businesses', MyBusiness.fromJson);

  Future<MyBusiness> business(String businessId) async =>
      MyBusiness.fromJson(await _send('/me/businesses/${_id(businessId)}'));

  Future<MyBusiness> register(
          {required String displayName,
          required String legalName,
          required String key}) async =>
      MyBusiness.fromJson(
          await _send('/me/businesses', method: 'POST', key: key, body: {
        'display_name': _clean(displayName, 'name', min: 2, max: 80),
        'legal_name': _clean(legalName, 'legal name', min: 2, max: 160),
      }));

  Future<BusinessProfile> profile(String businessId) async =>
      BusinessProfile.fromJson(
          await _send('/me/businesses/${_id(businessId)}/profile'));

  /// Only the fields passed are sent. Coordinates are never collected by this app.
  Future<ProfileRevision> editProfile(String businessId,
      {String? displayName,
      String? category,
      String? description,
      String? countyCode,
      String? city,
      String? addressLine,
      bool? addressPublic,
      List<ProfileContact>? contacts,
      required String key}) async {
    final changes = <String, Object?>{
      if (displayName != null)
        'display_name': _clean(displayName, 'name', min: 2, max: 80),
      if (category != null)
        'category': _slug.hasMatch(category)
            ? category
            : throw const FormatException('Invalid category'),
      if (description != null)
        'description':
            _clean(description, 'description', max: 2000, multiline: true),
      if (countyCode != null)
        'county_code': _code(countyCode, counties, 'county'),
      if (city != null) 'city': _clean(city, 'city', min: 1, max: 80),
      if (addressLine != null)
        'address_line': _clean(addressLine, 'address', max: 200),
      if (addressPublic != null) 'address_public': addressPublic,
      if (contacts != null)
        'contacts': [
          for (final c in contacts)
            {
              'kind': _code(c.kind, contactKinds, 'contact'),
              'value': _clean(c.value, 'contact', min: 1, max: 300),
              'is_public': c.isPublic
            }
        ],
    };
    if (changes.isEmpty) throw const FormatException('Nothing to change');
    return ProfileRevision.fromJson(await _send(
        '/me/businesses/${_id(businessId)}/profile',
        method: 'PATCH',
        key: key,
        body: changes));
  }

  Future<ProfileRevision> submitProfile(String businessId,
          {required String key}) async =>
      ProfileRevision.fromJson(await _send(
          '/me/businesses/${_id(businessId)}/profile/submit',
          method: 'POST',
          key: key,
          body: const {}));

  Future<BusinessHours> replaceHours(String businessId, List<HoursRule> rules,
          List<HoursException> exceptions, {required String key}) async =>
      BusinessHours.fromJson(await _send(
          '/me/businesses/${_id(businessId)}/hours',
          method: 'PUT',
          key: key,
          body: {
            'rules': [for (final r in rules) r.toJson()],
            'exceptions': [for (final e in exceptions) e.toJson()],
          }));

  Future<VerificationStatus> verificationStatus(String businessId) async =>
      VerificationStatus.fromJson(
          await _send('/me/businesses/${_id(businessId)}/verification'));

  List<Map<String, Object?>> _evidence(
      List<({String kind, String value})> evidence) {
    if (evidence.isEmpty || evidence.length > 5) {
      throw const FormatException('Invalid evidence');
    }
    return [
      for (final e in evidence)
        {
          'kind': _code(e.kind, evidenceKinds, 'evidence'),
          'value': _clean(e.value, 'evidence', min: 2, max: 300)
        }
    ];
  }

  /// Text evidence only: the service has no file evidence.
  Future<VerificationStatus> submitVerification(String businessId,
          {required String method,
          required List<({String kind, String value})> evidence,
          required String key}) async =>
      VerificationStatus.fromJson(await _send(
          '/me/businesses/${_id(businessId)}/verification',
          method: 'POST',
          key: key,
          body: {
            'method': _code(method, verificationMethods, 'method'),
            'declaration': true,
            'evidence': _evidence(evidence),
          }));

  Future<VerificationStatus> respondToVerification(String businessId,
          {required List<({String kind, String value})> evidence,
          required String key}) async =>
      VerificationStatus.fromJson(await _send(
          '/me/businesses/${_id(businessId)}/verification/evidence',
          method: 'POST',
          key: key,
          body: {'evidence': _evidence(evidence)}));

  Future<ListingStatus> listingStatus(String businessId) async =>
      ListingStatus.fromJson(
          await _send('/me/businesses/${_id(businessId)}/listing'));

  Future<ListingStatus> publish(String businessId,
          {required String key}) async =>
      ListingStatus.fromJson(await _send(
          '/me/businesses/${_id(businessId)}/listing/publish',
          method: 'POST',
          key: key,
          body: const {}));

  Future<ListingStatus> unpublish(String businessId,
          {required String key}) async =>
      ListingStatus.fromJson(await _send(
          '/me/businesses/${_id(businessId)}/listing/unpublish',
          method: 'POST',
          key: key,
          body: const {}));

  // ---- owner and staff: inbox -------------------------------------------------------------------------------------

  Future<ResultPage<BusinessInquiry>> inbox(String businessId,
          {String? cursor}) async =>
      ResultPage.parse(
          await _send('/me/businesses/${_id(businessId)}/inquiries',
              query: _page(cursor)),
          'inquiries',
          BusinessInquiry.fromJson);

  Future<BusinessInquiry> inboxThread(
          String businessId, String threadId) async =>
      BusinessInquiry.fromJson(await _send(
          '/me/businesses/${_id(businessId)}/inquiries/${_id(threadId)}'));

  Future<BusinessInquiry> reply(String businessId, String threadId, String body,
          {required String key}) async =>
      BusinessInquiry.fromJson(await _send(
          '/me/businesses/${_id(businessId)}/inquiries/${_id(threadId)}/messages',
          method: 'POST',
          key: key,
          body: {
            'body': _clean(body, 'message', min: 1, max: 1000, multiline: true)
          }));

  Future<BusinessInquiry> closeThread(String businessId, String threadId,
          {required String key}) async =>
      BusinessInquiry.fromJson(await _send(
          '/me/businesses/${_id(businessId)}/inquiries/${_id(threadId)}/close',
          method: 'POST',
          key: key,
          body: const {}));

  Future<BusinessInquiry> confirmThread(String businessId, String threadId,
          {required String key}) async =>
      BusinessInquiry.fromJson(await _send(
          '/me/businesses/${_id(businessId)}/inquiries/${_id(threadId)}/confirm',
          method: 'POST',
          key: key,
          body: const {}));

  /// Owner only. The customer is never told.
  Future<BusinessInquiry> blockCustomer(String businessId, String threadId,
          {required String key}) async =>
      BusinessInquiry.fromJson(await _send(
          '/me/businesses/${_id(businessId)}/inquiries/${_id(threadId)}/block',
          method: 'POST',
          key: key,
          body: const {}));

  // ---- owner: reviews and invitations -----------------------------------------------------------------------------

  Future<ResponseReceipt> respondToReview(
      String businessId, String reviewId, String body,
      {required String key}) async {
    final data = exact(
        await _send(
            '/me/businesses/${_id(businessId)}/reviews/${_id(reviewId)}/response',
            method: 'PUT',
            key: key,
            body: {
              'body':
                  _clean(body, 'response', min: 2, max: 1000, multiline: true)
            }),
        'response',
        {'review_id', 'body', 'created_at'});
    return ResponseReceipt(
        ident(data['review_id'], 'response'),
        text(data['body'], 'response', max: 1000),
        moment(data['created_at'], 'response'));
  }

  Future<void> deleteResponse(String businessId, String reviewId,
      {required String key}) async {
    _status(await _send(
        '/me/businesses/${_id(businessId)}/reviews/${_id(reviewId)}/response',
        method: 'DELETE',
        key: key));
  }

  Future<OneTimeCode<ReviewInvitation>> createReviewInvitation(
      String businessId,
      {required String key}) async {
    final data = exact(
        await _send('/me/businesses/${_id(businessId)}/review-invitations',
            method: 'POST', key: key, body: const {}),
        'invitation',
        {'id', 'expires_at', 'code'});
    return OneTimeCode(
        ReviewInvitation(ident(data['id'], 'invitation'),
            moment(data['expires_at'], 'invitation')),
        text(data['code'], 'invitation', min: 16, max: 64));
  }

  Future<void> revokeReviewInvitation(String businessId, String invitationId,
      {required String key}) async {
    final data = exact(
        await _send(
            '/me/businesses/${_id(businessId)}/review-invitations/${_id(invitationId)}',
            method: 'DELETE',
            key: key),
        'invitation',
        {'id', 'state'});
    ident(data['id'], 'invitation');
    text(data['state'], 'invitation', min: 1, max: 24);
  }

  // ---- owner and staff: team ----------------------------------------------------------------------------------------

  Future<Team> team(String businessId) async =>
      Team.fromJson(await _send('/me/businesses/${_id(businessId)}/members'));

  Future<OneTimeCode<StaffInvitation>> inviteStaff(
      String businessId, String label,
      {required String key}) async {
    final data = exact(
        await _send('/me/businesses/${_id(businessId)}/members/invitations',
            method: 'POST',
            key: key,
            body: {'label': _clean(label, 'label', min: 1, max: 40)}),
        'invitation',
        {'id', 'label', 'state', 'expires_at', 'code'});
    final invitation = StaffInvitation.fromMap({
      'id': data['id'],
      'label': data['label'],
      'state': data['state'],
      'expires_at': data['expires_at']
    });
    return OneTimeCode(
        invitation, text(data['code'], 'invitation', min: 16, max: 64));
  }

  Future<StaffInvitation> revokeInvitation(
          String businessId, String invitationId,
          {required String key}) async =>
      StaffInvitation.fromJson(await _send(
          '/me/businesses/${_id(businessId)}/members/invitations/${_id(invitationId)}',
          method: 'DELETE',
          key: key));

  /// A staff member accepts an invitation by entering the code they were given. The service answers an unknown,
  /// used, revoked or expired code identically.
  Future<MyBusiness> redeem(String code, {required String key}) async =>
      MyBusiness.fromJson(await _send('/me/business-invitations/redeem',
          method: 'POST',
          key: key,
          body: {'code': _clean(code, 'code', min: 16, max: 64)}));

  Future<void> leave(String businessId, {required String key}) async {
    _status(await _send('/me/businesses/${_id(businessId)}/leave',
        method: 'POST', key: key, body: const {}));
  }

  static void _status(Map<String, dynamic> data) {
    text(exact(data, 'status', {'status'})['status'], 'status',
        min: 1, max: 24);
  }
}
