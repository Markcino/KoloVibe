import 'business_json.dart';

// ---- discovery -------------------------------------------------------------------------------------------------

class CategoryRef {
  const CategoryRef(this.slug, this.name);
  final String slug;
  final String name;
  factory CategoryRef.fromJson(Object? value) {
    final data = exact(value, 'category', {'slug', 'name'});
    return CategoryRef(text(data['slug'], 'category', min: 2, max: 60),
        text(data['name'], 'category', min: 1, max: 80));
  }
}

class BusinessCategory {
  const BusinessCategory(this.slug, this.name, this.parent);
  final String slug;
  final String name;
  final String? parent;
  factory BusinessCategory.fromJson(Object? value) {
    final data = exact(value, 'category', {'slug', 'name', 'active', 'parent'});
    flag(data['active'], 'category');
    return BusinessCategory(
        text(data['slug'], 'category', min: 2, max: 60),
        text(data['name'], 'category', min: 1, max: 80),
        textOrNull(data['parent'], 'category', min: 2, max: 60));
  }
}

class ResultPage<T> {
  const ResultPage(this.items, this.nextCursor);
  final List<T> items;
  final String? nextCursor;
  static ResultPage<T> parse<T>(
      Object? value, String what, T Function(Object?) item) {
    final data = exact(value, what, {'items', 'next_cursor'});
    return ResultPage(listOf(data['items'], what, item, max: 100),
        cursor(data['next_cursor'], what));
  }
}

class BusinessCard {
  const BusinessCard(this.id, this.name, this.category, this.countyCode,
      this.city, this.summary, this.verified, this.openNow);
  final String id;
  final String name;
  final CategoryRef category;
  final String countyCode;
  final String city;
  final String summary;
  final bool verified;

  /// Null when the business has not published hours: unknown is not "closed".
  final bool? openNow;
  static const keys = {
    'id',
    'display_name',
    'category',
    'county_code',
    'city',
    'summary',
    'verified',
    'open_now'
  };
  factory BusinessCard.fromMap(Map<String, dynamic> data) => BusinessCard(
      ident(data['id'], 'business'),
      text(data['display_name'], 'business', min: 1, max: 80),
      CategoryRef.fromJson(data['category']),
      text(data['county_code'], 'business', max: 40),
      text(data['city'], 'business', max: 80),
      text(data['summary'], 'business', max: 2000),
      flag(data['verified'], 'business'),
      data['open_now'] == null ? null : flag(data['open_now'], 'business'));
  factory BusinessCard.fromJson(Object? value) =>
      BusinessCard.fromMap(exact(value, 'business', keys));
}

class HoursRule {
  const HoursRule(this.weekday, this.opens, this.closes);
  final int weekday;
  final String opens;
  final String closes;
  factory HoursRule.fromJson(Object? value) {
    final data = exact(value, 'hours', {'weekday', 'opens', 'closes'});
    return HoursRule(whole(data['weekday'], 'hours', max: 6),
        _clock(data['opens']), _clock(data['closes']));
  }
  Map<String, Object?> toJson() =>
      {'weekday': weekday, 'opens': opens, 'closes': closes};
}

String _clock(Object? value) {
  final result = text(value, 'hours', min: 5, max: 5);
  if (!RegExp(r'^([01]\d|2[0-4]):[0-5]\d$').hasMatch(result)) {
    throw const FormatException('Invalid hours');
  }
  return result;
}

class HoursException {
  const HoursException(this.onDate, this.closed, this.opens, this.closes);
  final String onDate;
  final bool closed;
  final String? opens;
  final String? closes;
  factory HoursException.fromJson(Object? value) {
    final data = exact(value, 'hours', {'on_date', 'closed'},
        optional: {'opens', 'closes'});
    final date = text(data['on_date'], 'hours', min: 10, max: 10);
    if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(date)) {
      throw const FormatException('Invalid hours');
    }
    final closed = flag(data['closed'], 'hours');
    if (closed != (data['opens'] == null && data['closes'] == null)) {
      throw const FormatException('Invalid hours');
    }
    return HoursException(
        date,
        closed,
        data['opens'] == null ? null : _clock(data['opens']),
        data['closes'] == null ? null : _clock(data['closes']));
  }
  Map<String, Object?> toJson() => {
        'on_date': onDate,
        'closed': closed,
        if (!closed) 'opens': opens,
        if (!closed) 'closes': closes,
      };
}

class BusinessHours {
  const BusinessHours(this.rules, this.exceptions);
  final List<HoursRule> rules;
  final List<HoursException> exceptions;
  bool get isEmpty => rules.isEmpty && exceptions.isEmpty;
  factory BusinessHours.fromJson(Object? value) {
    final data = exact(value, 'hours', {'rules', 'exceptions'});
    return BusinessHours(
        listOf(data['rules'], 'hours', HoursRule.fromJson, max: 28),
        listOf(data['exceptions'], 'hours', HoursException.fromJson, max: 60));
  }
}

class Rating {
  const Rating(this.count, this.average);
  final int count;

  /// Null until the owner sets a minimum number of reviews: only the count is shown.
  final double? average;
  factory Rating.fromJson(Object? value) {
    final data = exact(value, 'rating', {'count', 'average'});
    final average = data['average'];
    if (average != null && (average is! num || average < 1 || average > 5)) {
      throw const FormatException('Invalid rating');
    }
    return Rating(
        whole(data['count'], 'rating'), (average as num?)?.toDouble());
  }
}

class ContactValue {
  const ContactValue(this.kind, this.value);
  final String kind;
  final String value;
}

enum ContactAccess {
  none,
  signInRequired,
  verifiedEmailRequired,
  limitReached,
  available
}

class BusinessDetail {
  const BusinessDetail(this.card, this.rating, this.description,
      this.addressLine, this.timeZone, this.hours, this.contacts, this.access);
  final BusinessCard card;
  final Rating rating;
  final String description;
  final String? addressLine;
  final String timeZone;
  final BusinessHours hours;
  final List<ContactValue>? contacts;
  final ContactAccess access;
  factory BusinessDetail.fromJson(Object? value) {
    final data = exact(value, 'business', {
      ...BusinessCard.keys,
      'rating',
      'description',
      'address_line',
      'time_zone',
      'hours',
      'contacts',
      'contacts_access'
    });
    final access = choice(data['contacts_access'], 'business', const {
      'none': ContactAccess.none,
      'sign_in_required': ContactAccess.signInRequired,
      'verified_email_required': ContactAccess.verifiedEmailRequired,
      'limit_reached': ContactAccess.limitReached,
      'available': ContactAccess.available,
    });
    final raw = data['contacts'];
    final contacts = raw == null
        ? null
        : listOf(raw, 'business', (Object? entry) {
            final contact = exact(entry, 'contact', {'kind', 'value'});
            return ContactValue(
                text(contact['kind'], 'contact', min: 1, max: 16),
                text(contact['value'], 'contact', min: 1, max: 300));
          }, max: 10);
    // A service answer that discloses contacts without saying access is available is not trusted.
    if ((contacts != null) !=
        (access == ContactAccess.available || access == ContactAccess.none)) {
      throw const FormatException('Invalid business');
    }
    if (access == ContactAccess.none &&
        contacts != null &&
        contacts.isNotEmpty) {
      throw const FormatException('Invalid business');
    }
    final card = BusinessCard.fromMap(
        {for (final key in BusinessCard.keys) key: data[key]});
    return BusinessDetail(
        card,
        Rating.fromJson(data['rating']),
        text(data['description'], 'business', max: 2000),
        textOrNull(data['address_line'], 'business', max: 200),
        text(data['time_zone'], 'business', min: 1, max: 64),
        BusinessHours.fromJson(data['hours']),
        contacts,
        access);
  }
}

// ---- reviews ---------------------------------------------------------------------------------------------------

enum ReviewBasis { interactionConfirmed, invited, open }

ReviewBasis _basis(Object? value) => choice(value, 'review', const {
      'interaction_confirmed': ReviewBasis.interactionConfirmed,
      'invited': ReviewBasis.invited,
      'open': ReviewBasis.open,
    });

class OwnerResponse {
  const OwnerResponse(this.body, this.createdAt);
  final String body;
  final DateTime createdAt;
}

class PublicReview {
  const PublicReview(
      this.id,
      this.rating,
      this.title,
      this.body,
      this.authorLabel,
      this.basis,
      this.createdAt,
      this.editedAt,
      this.response);
  final String id;
  final int rating;
  final String? title;
  final String body;
  final String authorLabel;
  final ReviewBasis basis;
  final DateTime createdAt;
  final DateTime? editedAt;
  final OwnerResponse? response;
  factory PublicReview.fromJson(Object? value) {
    final data = exact(value, 'review', {
      'id',
      'rating',
      'title',
      'body',
      'author_label',
      'basis',
      'created_at',
      'edited_at',
      'response'
    });
    final response = data['response'];
    return PublicReview(
        ident(data['id'], 'review'),
        whole(data['rating'], 'review', min: 1, max: 5),
        textOrNull(data['title'], 'review', max: 100),
        text(data['body'], 'review', max: 2000),
        text(data['author_label'], 'review', min: 1, max: 80),
        _basis(data['basis']),
        moment(data['created_at'], 'review'),
        momentOrNull(data['edited_at'], 'review'),
        response == null
            ? null
            : () {
                final map = exact(response, 'review', {'body', 'created_at'});
                return OwnerResponse(text(map['body'], 'review', max: 1000),
                    moment(map['created_at'], 'review'));
              }());
  }
}

enum ReviewState { published, held, removed, withdrawn }

class OwnReview {
  const OwnReview(this.id, this.businessId, this.rating, this.title, this.body,
      this.state, this.basis, this.createdAt, this.editedAt);
  final String id;
  final String businessId;
  final int rating;
  final String? title;
  final String body;
  final ReviewState state;
  final ReviewBasis basis;
  final DateTime createdAt;
  final DateTime? editedAt;
  factory OwnReview.fromJson(Object? value) {
    final data = exact(value, 'review', {
      'id',
      'business_id',
      'rating',
      'title',
      'body',
      'state',
      'basis',
      'created_at',
      'edited_at'
    });
    return OwnReview(
        ident(data['id'], 'review'),
        ident(data['business_id'], 'review'),
        whole(data['rating'], 'review', min: 1, max: 5),
        textOrNull(data['title'], 'review', max: 100),
        text(data['body'], 'review', max: 2000),
        choice(data['state'], 'review', const {
          'published': ReviewState.published,
          'held': ReviewState.held,
          'removed': ReviewState.removed,
          'withdrawn': ReviewState.withdrawn,
        }),
        _basis(data['basis']),
        moment(data['created_at'], 'review'),
        momentOrNull(data['edited_at'], 'review'));
  }
}

// ---- inquiries -------------------------------------------------------------------------------------------------

enum InquiryState { open, closedByCustomer, closedByBusiness, blocked }

InquiryState _inquiryState(Object? value) => choice(value, 'inquiry', const {
      'open': InquiryState.open,
      'closed_by_customer': InquiryState.closedByCustomer,
      'closed_by_business': InquiryState.closedByBusiness,
      'blocked': InquiryState.blocked,
    });

class InquiryMessage {
  const InquiryMessage(
      this.id, this.fromBusiness, this.body, this.removed, this.createdAt);
  final String id;
  final bool fromBusiness;

  /// Null when a moderator removed the message.
  final String? body;
  final bool removed;
  final DateTime createdAt;
  factory InquiryMessage.fromJson(Object? value) {
    final data = exact(value, 'message',
        {'id', 'author_kind', 'body', 'removed', 'created_at'});
    final removed = flag(data['removed'], 'message');
    final body = textOrNull(data['body'], 'message', max: 1000);
    if (removed != (body == null)) {
      throw const FormatException('Invalid message');
    }
    return InquiryMessage(
        ident(data['id'], 'message'),
        choice(data['author_kind'], 'message',
            const {'customer': false, 'business': true}),
        body,
        removed,
        moment(data['created_at'], 'message'));
  }
}

class Confirmation {
  const Confirmation(this.customer, this.business);
  final bool customer;
  final bool business;
  factory Confirmation.fromJson(Object? value) {
    final data = exact(value, 'inquiry', {'customer', 'business'});
    return Confirmation(
        flag(data['customer'], 'inquiry'), flag(data['business'], 'inquiry'));
  }
}

/// A conversation as the customer sees it. [messages] is empty in list rows.
class CustomerInquiry {
  const CustomerInquiry(this.id, this.businessId, this.businessName, this.state,
      this.subjectCode, this.createdAt, this.confirmed, this.messages);
  final String id;
  final String businessId;
  final String businessName;
  final InquiryState state;
  final String? subjectCode;
  final DateTime createdAt;
  final Confirmation confirmed;
  final List<InquiryMessage> messages;
  factory CustomerInquiry.fromJson(Object? value) {
    final data = exact(value, 'inquiry', {
      'id',
      'business_id',
      'business_name',
      'state',
      'subject_code',
      'confirmed',
      'created_at'
    }, optional: {
      'messages'
    });
    return CustomerInquiry(
        ident(data['id'], 'inquiry'),
        ident(data['business_id'], 'inquiry'),
        text(data['business_name'], 'inquiry', min: 1, max: 80),
        _inquiryState(data['state']),
        textOrNull(data['subject_code'], 'inquiry', max: 40),
        moment(data['created_at'], 'inquiry'),
        Confirmation.fromJson(data['confirmed']),
        data['messages'] == null
            ? const []
            : listOf(data['messages'], 'inquiry', InquiryMessage.fromJson,
                max: 100));
  }
}

/// A conversation as the business sees it: the customer is only ever a label.
class BusinessInquiry {
  const BusinessInquiry(this.id, this.customerLabel, this.state,
      this.subjectCode, this.createdAt, this.confirmed, this.messages);
  final String id;
  final String customerLabel;
  final InquiryState state;
  final String? subjectCode;
  final DateTime createdAt;
  final Confirmation confirmed;
  final List<InquiryMessage> messages;
  factory BusinessInquiry.fromJson(Object? value) {
    final data = exact(value, 'inquiry', {
      'id',
      'customer_label',
      'state',
      'subject_code',
      'created_at',
      'confirmed'
    }, optional: {
      'messages'
    });
    return BusinessInquiry(
        ident(data['id'], 'inquiry'),
        text(data['customer_label'], 'inquiry', min: 1, max: 40),
        _inquiryState(data['state']),
        textOrNull(data['subject_code'], 'inquiry', max: 40),
        moment(data['created_at'], 'inquiry'),
        Confirmation.fromJson(data['confirmed']),
        data['messages'] == null
            ? const []
            : listOf(data['messages'], 'inquiry', InquiryMessage.fromJson,
                max: 100));
  }
}

class ReportReceipt {
  const ReportReceipt(this.id, this.state);
  final String id;
  final String state;
  factory ReportReceipt.fromJson(Object? value) {
    final data = exact(value, 'report', {'id', 'state'});
    return ReportReceipt(ident(data['id'], 'report'),
        text(data['state'], 'report', min: 1, max: 24));
  }
}

// ---- owner and staff -------------------------------------------------------------------------------------------

enum BusinessRole { owner, staff }

class MyBusiness {
  const MyBusiness(this.id, this.name, this.state, this.role, this.verified,
      this.createdAt, this.legalName);
  final String id;
  final String name;
  final String state;
  final BusinessRole role;
  final bool verified;
  final DateTime createdAt;

  /// Present for owners only; the service never sends it to staff.
  final String? legalName;
  bool get isOwner => role == BusinessRole.owner;
  factory MyBusiness.fromJson(Object? value) {
    final data = exact(value, 'business', {
      'id',
      'state',
      'my_role',
      'verified',
      'listed',
      'display_name',
      'created_at'
    }, optional: {
      'legal_name'
    });
    flag(data['listed'], 'business');
    final role = choice(data['my_role'], 'business',
        const {'owner': BusinessRole.owner, 'staff': BusinessRole.staff});
    if ((role == BusinessRole.owner) != data.containsKey('legal_name')) {
      throw const FormatException('Invalid business');
    }
    return MyBusiness(
        ident(data['id'], 'business'),
        text(data['display_name'], 'business', min: 1, max: 80),
        choice(data['state'], 'business', const {
          'draft': 'draft',
          'submitted': 'submitted',
          'under_review': 'under_review',
          'needs_info': 'needs_info',
          'verified': 'verified',
          'rejected': 'rejected',
          'suspended': 'suspended',
          'revoked': 'revoked',
          'closed': 'closed',
        }),
        role,
        flag(data['verified'], 'business'),
        moment(data['created_at'], 'business'),
        textOrNull(data['legal_name'], 'business', min: 1, max: 160));
  }
}

class ProfileContact {
  const ProfileContact(this.kind, this.value, this.isPublic);
  final String kind;
  final String value;
  final bool isPublic;
  Map<String, Object?> toJson() =>
      {'kind': kind, 'value': value, 'is_public': isPublic};
  factory ProfileContact.fromJson(Object? value) {
    final data = exact(value, 'contact', {'kind', 'value', 'is_public'});
    return ProfileContact(
        text(data['kind'], 'contact', min: 1, max: 16),
        text(data['value'], 'contact', min: 1, max: 300),
        flag(data['is_public'], 'contact'));
  }
}

class ProfileRevision {
  const ProfileRevision(
      {required this.id,
      required this.number,
      required this.state,
      required this.name,
      required this.category,
      required this.description,
      required this.countyCode,
      required this.city,
      required this.addressLine,
      required this.addressPublic,
      required this.contacts,
      required this.timeZone,
      required this.reasonCode,
      required this.changedFields,
      required this.applied});
  final String id;
  final int number;
  final String state;
  final String name;
  final String? category;
  final String description;
  final String countyCode;
  final String city;
  final String addressLine;
  final bool addressPublic;
  final List<ProfileContact> contacts;
  final String timeZone;
  final String? reasonCode;
  final List<String> changedFields;

  /// Only on a submit answer: true when the change went live without review.
  final bool? applied;
  static const keys = {
    'id',
    'revision_no',
    'state',
    'display_name',
    'category',
    'description',
    'county_code',
    'city',
    'address_line',
    'address_public',
    'latitude',
    'longitude',
    'coordinates_public',
    'time_zone',
    'contacts',
    'reason_code'
  };
  factory ProfileRevision.fromJson(Object? value) {
    final data =
        exact(value, 'profile', keys, optional: {'changed_fields', 'applied'});
    // Coordinates are never collected or shown in this app.
    return ProfileRevision(
        id: ident(data['id'], 'profile'),
        number: whole(data['revision_no'], 'profile', min: 1),
        state: choice(data['state'], 'profile', const {
          'draft': 'draft',
          'pending_review': 'pending_review',
          'approved': 'approved',
          'rejected': 'rejected',
          'superseded': 'superseded',
        }),
        name: text(data['display_name'], 'profile', min: 1, max: 80),
        category: textOrNull(data['category'], 'profile', min: 2, max: 60),
        description: text(data['description'], 'profile', max: 2000),
        countyCode: text(data['county_code'], 'profile', max: 40),
        city: text(data['city'], 'profile', max: 80),
        addressLine: text(data['address_line'], 'profile', max: 200),
        addressPublic: flag(data['address_public'], 'profile'),
        contacts: listOf(data['contacts'], 'profile', ProfileContact.fromJson,
            max: 10),
        timeZone: text(data['time_zone'], 'profile', min: 1, max: 64),
        reasonCode: textOrNull(data['reason_code'], 'profile', max: 40),
        changedFields: data['changed_fields'] == null
            ? const []
            : listOf(data['changed_fields'], 'profile',
                (Object? v) => text(v, 'profile', min: 1, max: 40), max: 30),
        applied:
            data['applied'] == null ? null : flag(data['applied'], 'profile'));
  }
}

class BusinessProfile {
  const BusinessProfile(
      this.approved, this.working, this.lastRejected, this.hours);
  final ProfileRevision? approved;
  final ProfileRevision? working;
  final ProfileRevision? lastRejected;
  final BusinessHours hours;
  factory BusinessProfile.fromJson(Object? value) {
    final data = exact(
        value, 'profile', {'approved', 'working', 'last_rejected', 'hours'});
    ProfileRevision? revision(Object? v) =>
        v == null ? null : ProfileRevision.fromJson(v);
    return BusinessProfile(
        revision(data['approved']),
        revision(data['working']),
        revision(data['last_rejected']),
        BusinessHours.fromJson(data['hours']));
  }
}

class VerificationStatus {
  const VerificationStatus(
      this.state, this.submittedAt, this.decidedAt, this.reasonCode);
  final String state;
  final DateTime? submittedAt;
  final DateTime? decidedAt;
  final String? reasonCode;
  bool get none => state == 'none';
  factory VerificationStatus.fromJson(Object? value) {
    final data = exact(value, 'verification',
        {'state', 'submitted_at', 'decided_at', 'reason_code'});
    return VerificationStatus(
        choice(data['state'], 'verification', const {
          'none': 'none',
          'submitted': 'submitted',
          'under_review': 'under_review',
          'needs_info': 'needs_info',
          'verified': 'verified',
          'rejected': 'rejected',
          'revoked': 'revoked',
        }),
        momentOrNull(data['submitted_at'], 'verification'),
        momentOrNull(data['decided_at'], 'verification'),
        textOrNull(data['reason_code'], 'verification', max: 40));
  }
}

class ListingStatus {
  const ListingStatus(
      this.listed, this.ownerWantsListing, this.eligible, this.reasons);
  final bool listed;
  final bool ownerWantsListing;
  final bool eligible;
  final List<String> reasons;
  factory ListingStatus.fromJson(Object? value) {
    final data = exact(value, 'listing',
        {'listed', 'owner_wants_listing', 'eligible', 'reasons'});
    return ListingStatus(
        flag(data['listed'], 'listing'),
        flag(data['owner_wants_listing'], 'listing'),
        flag(data['eligible'], 'listing'),
        listOf(data['reasons'], 'listing',
            (Object? v) => text(v, 'listing', min: 1, max: 40),
            max: 20));
  }
}

class Member {
  const Member(this.id, this.role, this.label, this.since, this.isYou);
  final String id;
  final BusinessRole role;
  final String label;
  final DateTime since;
  final bool isYou;
}

class StaffInvitation {
  const StaffInvitation(this.id, this.label, this.state, this.expiresAt);
  final String id;
  final String label;
  final String state;
  final DateTime expiresAt;
  factory StaffInvitation.fromJson(Object? value) => StaffInvitation.fromMap(
      exact(value, 'invitation', {'id', 'label', 'state', 'expires_at'}));
  factory StaffInvitation.fromMap(Map<String, dynamic> data) => StaffInvitation(
      ident(data['id'], 'invitation'),
      text(data['label'], 'invitation', min: 1, max: 40),
      choice(data['state'], 'invitation', const {
        'pending': 'pending',
        'redeemed': 'redeemed',
        'revoked': 'revoked',
        'expired': 'expired'
      }),
      moment(data['expires_at'], 'invitation'));
}

class Team {
  const Team(this.members, this.invitations);
  final List<Member> members;
  final List<StaffInvitation> invitations;
  factory Team.fromJson(Object? value) {
    final data = exact(value, 'team', {'members', 'invitations'});
    return Team(
        listOf(data['members'], 'team', (Object? entry) {
          final member =
              exact(entry, 'team', {'id', 'role', 'label', 'since', 'is_you'});
          return Member(
              ident(member['id'], 'team'),
              choice(member['role'], 'team', const {
                'owner': BusinessRole.owner,
                'staff': BusinessRole.staff
              }),
              text(member['label'], 'team', max: 40),
              moment(member['since'], 'team'),
              flag(member['is_you'], 'team'));
        }, max: 50),
        listOf(data['invitations'], 'team', StaffInvitation.fromJson, max: 50));
  }
}

/// A code the service shows once. It is held in memory by the screen that created it and never stored or logged.
class OneTimeCode<T> {
  const OneTimeCode(this.value, this.code);
  final T value;
  final String code;
  @override
  String toString() => 'OneTimeCode(hidden)';
}

class ReviewInvitation {
  const ReviewInvitation(this.id, this.expiresAt);
  final String id;
  final DateTime expiresAt;
}

class ResponseReceipt {
  const ResponseReceipt(this.reviewId, this.body, this.createdAt);
  final String reviewId;
  final String body;
  final DateTime createdAt;
}
