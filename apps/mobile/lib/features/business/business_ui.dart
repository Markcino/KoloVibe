import 'package:flutter/material.dart';

import '../../core/network/api_client.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/kolo_components.dart';
import '../../shared/widgets/live_state_view.dart';
import 'business_lists.dart';
import 'business_models.dart';
import 'live_business_repository.dart';

/// Loads once, shows the shared loading / failure states, and lets the user retry. With [inline] the states are
/// compact cards so one failing section never hides the rest of a screen.
class BusinessLoader<T> extends StatefulWidget {
  const BusinessLoader({
    super.key,
    required this.load,
    required this.builder,
    this.onSignIn,
    this.inline = false,
    this.errorBuilder,
  });
  final Future<T> Function() load;

  /// Lets a screen replace the standard failure view for a particular error; return null to keep the standard one.
  final Widget? Function(BuildContext context, Object error)? errorBuilder;
  final Widget Function(BuildContext context, T value, VoidCallback reload)
      builder;
  final VoidCallback? onSignIn;
  final bool inline;

  @override
  State<BusinessLoader<T>> createState() => _BusinessLoaderState<T>();
}

class _BusinessLoaderState<T> extends State<BusinessLoader<T>> {
  late Future<T> _future = widget.load();

  void _reload() {
    setState(() {
      _future = widget.load();
    });
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<T>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return widget.inline
                ? const KoloSkeleton(height: 72)
                : const LiveStateView.loading();
          }
          if (snapshot.hasError) {
            if (widget.inline) {
              return KoloInlineState(
                title: 'Could not load this',
                message: 'Check your connection, then try again.',
                icon: Icons.error_outline,
                actionLabel: 'Try again',
                onAction: _reload,
              );
            }
            return widget.errorBuilder?.call(context, snapshot.error!) ??
                LiveStateView.failure(snapshot.error!,
                    onRetry: _reload, onSignIn: widget.onSignIn);
          }
          return widget.builder(context, snapshot.data as T, _reload);
        },
      );
}

/// A list that loads page by page with an explicit "Show more" control. Give it a new [key] to start again.
class BusinessPagedList<T> extends StatefulWidget {
  const BusinessPagedList({
    super.key,
    required this.fetch,
    required this.itemBuilder,
    required this.empty,
    this.header,
    this.onSignIn,
    this.padding = const EdgeInsets.fromLTRB(20, 8, 20, 24),
  });
  final Future<ResultPage<T>> Function(String? cursor) fetch;
  final Widget Function(BuildContext context, T item) itemBuilder;
  final Widget empty;
  final Widget? header;
  final VoidCallback? onSignIn;
  final EdgeInsets padding;

  @override
  State<BusinessPagedList<T>> createState() => _BusinessPagedListState<T>();
}

class _BusinessPagedListState<T> extends State<BusinessPagedList<T>> {
  final List<T> _items = [];
  String? _cursor;
  Object? _error;
  bool _loading = true;
  bool _moreFailed = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final more = _items.isNotEmpty;
    setState(() {
      _loading = true;
      _moreFailed = false;
      if (!more) _error = null;
    });
    try {
      final page = await widget.fetch(more ? _cursor : null);
      if (!mounted) return;
      setState(() {
        _items.addAll(page.items);
        _cursor = page.nextCursor;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        if (more) {
          _moreFailed = true;
        } else {
          _error = error;
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_items.isEmpty && _loading) return const LiveStateView.loading();
    if (_items.isEmpty && _error != null) {
      return LiveStateView.failure(_error!,
          onRetry: _load, onSignIn: widget.onSignIn);
    }
    return ListView(
      padding: widget.padding,
      children: [
        if (widget.header != null) widget.header!,
        if (_items.isEmpty) widget.empty,
        for (final item in _items) widget.itemBuilder(context, item),
        if (_moreFailed)
          KoloInlineState(
            title: 'Could not load more',
            message: 'Check your connection, then try again.',
            icon: Icons.error_outline,
            actionLabel: 'Try again',
            onAction: _load,
          )
        else if (_cursor != null)
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Align(
              child: _loading
                  ? const SizedBox(
                      width: 24,
                      height: 24,
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : KoloPillButton(label: 'Show more', onPressed: _load),
            ),
          ),
      ],
    );
  }
}

// ---- wording ---------------------------------------------------------------------------------------------------

String countyLabel(String code) => labelFor(counties, code);

String openLabel(bool? openNow) => switch (openNow) {
      true => 'Open now',
      false => 'Closed now',
      null => 'Opening hours not published',
    };

String ratingLabel(Rating rating) {
  if (rating.count == 0) return 'No reviews yet';
  final noun = rating.count == 1 ? 'review' : 'reviews';
  final average = rating.average;
  return average == null
      ? '${rating.count} $noun'
      : '${average.toStringAsFixed(1)} out of 5 · ${rating.count} $noun';
}

String starsLabel(int rating) => '$rating out of 5';

String reviewBasisLabel(ReviewBasis basis) => switch (basis) {
      ReviewBasis.interactionConfirmed => 'Interaction confirmed',
      ReviewBasis.invited => 'Invited by the business',
      ReviewBasis.open => 'Open review',
    };

const _months = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
];

String dateLabel(DateTime when) {
  final local = when.toLocal();
  return '${local.day} ${_months[local.month - 1]} ${local.year}';
}

// ---- shared pieces ---------------------------------------------------------------------------------------------

/// One business in a list: name, verified mark, place, open state and summary. Plain text only.
class BusinessCardTile extends StatelessWidget {
  const BusinessCardTile({super.key, required this.card, required this.onTap});
  final BusinessCard card;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final place = [card.city, countyLabel(card.countyCode)]
        .where((part) => part.isNotEmpty)
        .join(', ');
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Semantics(
        button: true,
        label: [
          card.name,
          if (card.verified) 'Verified',
          card.category.name,
          if (place.isNotEmpty) place,
          openLabel(card.openNow),
        ].join('. '),
        excludeSemantics: true,
        child: Material(
          color: Colors.white,
          shape: RoundedRectangleBorder(
              side: const BorderSide(color: KoloVibeColors.line),
              borderRadius: BorderRadius.circular(KoloVibeRadii.tile)),
          child: InkWell(
            borderRadius: BorderRadius.circular(KoloVibeRadii.tile),
            onTap: onTap,
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    Expanded(
                      child: Text(card.name,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: KoloVibeText.body(16,
                              weight: FontWeight.w700,
                              color: KoloVibeColors.navy)),
                    ),
                    if (card.verified) ...[
                      const SizedBox(width: 8),
                      const KoloBadge('Verified', filled: true),
                    ],
                  ]),
                  const SizedBox(height: 4),
                  Text(
                      [card.category.name, if (place.isNotEmpty) place]
                          .join(' · '),
                      style: KoloVibeText.body(13)),
                  const SizedBox(height: 4),
                  Text(openLabel(card.openNow),
                      style: KoloVibeText.body(12,
                          weight: FontWeight.w600,
                          color: card.openNow == true
                              ? KoloVibeColors.green
                              : KoloVibeColors.muted)),
                  if (card.summary.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Text(card.summary,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: KoloVibeText.body(13, height: 1.4)),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Search words and filters carried between the Business results (M-111) and filter (M-112) screens in the
/// route's one string. Decoding re-validates everything, so a hand-made route cannot inject anything.
class BusinessFilters {
  const BusinessFilters(
      {this.query,
      this.category,
      this.county,
      this.openNow = false,
      this.verifiedOnly = false});
  final String? query;
  final String? category;
  final String? county;
  final bool openNow;
  final bool verifiedOnly;

  static final _slug = RegExp(r'^[a-z0-9-]{2,60}$');

  bool get isEmpty => this == const BusinessFilters();

  /// Filters other than the search words.
  int get active =>
      (category != null ? 1 : 0) +
      (county != null ? 1 : 0) +
      (openNow ? 1 : 0) +
      (verifiedOnly ? 1 : 0);

  String? encode() {
    final params = {
      if (query != null) 'q': query!,
      if (category != null) 'category': category!,
      if (county != null) 'county': county!,
      if (openNow) 'open': '1',
      if (verifiedOnly) 'verified': '1',
    };
    return params.isEmpty ? null : Uri(queryParameters: params).query;
  }

  factory BusinessFilters.decode(String? raw) {
    if (raw == null || raw.isEmpty || raw.length > 400) {
      return const BusinessFilters();
    }
    try {
      final data = Uri.splitQueryString(raw);
      final query = data['q']?.trim();
      final category = data['category'];
      final county = data['county'];
      return BusinessFilters(
        query:
            query == null || query.isEmpty || query.length > 100 ? null : query,
        category:
            category != null && _slug.hasMatch(category) ? category : null,
        county: counties.any((c) => c.code == county) ? county : null,
        openNow: data['open'] == '1',
        verifiedOnly: data['verified'] == '1',
      );
    } on FormatException {
      return const BusinessFilters();
    } on ArgumentError {
      // Uri.splitQueryString reports bad percent-encoding this way.
      return const BusinessFilters();
    }
  }

  BusinessFilters copyWith(
          {Object? query = _keep,
          Object? category = _keep,
          Object? county = _keep,
          bool? openNow,
          bool? verifiedOnly}) =>
      BusinessFilters(
        query: identical(query, _keep) ? this.query : query as String?,
        category:
            identical(category, _keep) ? this.category : category as String?,
        county: identical(county, _keep) ? this.county : county as String?,
        openNow: openNow ?? this.openNow,
        verifiedOnly: verifiedOnly ?? this.verifiedOnly,
      );

  @override
  bool operator ==(Object other) =>
      other is BusinessFilters &&
      other.query == query &&
      other.category == category &&
      other.county == county &&
      other.openNow == openNow &&
      other.verifiedOnly == verifiedOnly;

  @override
  int get hashCode =>
      Object.hash(query, category, county, openNow, verifiedOnly);

  static const Object _keep = Object();
}

// ---- sending things --------------------------------------------------------------------------------------------

/// One idempotency key per attempt. Retrying the same content re-sends the same key, so a request that did reach the
/// service but whose answer was lost is replayed, not applied twice; changed content gets a new key.
class AttemptKey {
  String? _fingerprint;
  String? _key;
  String forContent(String fingerprint) {
    if (_fingerprint != fingerprint || _key == null) {
      _fingerprint = fingerprint;
      _key = LiveBusinessRepository.newKey();
    }
    return _key!;
  }

  void reset() {
    _fingerprint = null;
    _key = null;
  }
}

/// What a refused or failed send says, in words a customer can act on. Known service reason codes get their own
/// sentence; everything else is generic and never shows raw service text for server errors.
String failureText(Object error) {
  if (error is FormatException || error is ArgumentError) {
    return 'Check what you entered and try again.';
  }
  if (error is! ApiFailure) return 'Something went wrong. Please try again.';
  switch (error.code) {
    case 'thread_full':
      return 'This conversation has reached its message limit.';
    case 'thread_exists':
      return 'You already have an open conversation with this business.';
    case 'thread_closed':
      return 'This conversation is closed.';
    case 'no_exchange':
      return 'You and the business both need to have written before this can be confirmed.';
    case 'interaction_not_confirmed':
      return 'That conversation has not been confirmed by both you and the business.';
    case 'already_reviewed':
      return 'You have already reviewed this business.';
    case 'not_editable':
      return 'This review can no longer be changed.';
    case 'own_content':
      return 'You cannot report your own content.';
    case 'already_reported':
      return 'You have already reported this.';
    case 'invitation_redeemed':
      return 'This invitation code has already been used.';
    case 'invitation_required':
      return 'Registering a business is by invitation only during the pilot, and your account has not been invited.';
    case 'business_limit':
      return 'You have reached the most businesses one account can register.';
    case 'business_closed':
      return 'This business is closed, so it cannot be changed.';
    case 'staff_limit':
      return 'This business has reached its limit of team members and invitations.';
    case 'already_member':
      return 'You are already a member of this business.';
    case 'owner_protected':
      return 'An owner cannot be removed from or leave a business.';
    case 'revision_pending':
      return 'A change is already waiting for review. Wait for the decision before changing the profile again.';
    case 'unknown_category':
      return 'That category is not available. Choose another.';
    case 'no_draft':
      return 'There is no saved change to submit. Edit the profile first.';
    case 'no_changes':
      return 'Nothing has changed since the last approved profile.';
    case 'incomplete_profile':
      return 'The profile is incomplete. Fill in every required field, then submit again.';
    case 'step_up_unavailable':
      return 'This change needs an extra security check that is not available yet.';
    case 'use_respond':
      return 'KoloVibe has asked for more information. Answer that request instead.';
    case 'no_open_request':
      return 'There is no open request for information.';
    case 'invalid_transition':
      return 'That is not possible at this stage of verification.';
    case 'invitation_limit':
      return 'There are too many open invitations. Revoke one first.';
    case 'response_removed':
      return 'KoloVibe reviewers removed this reply, so it cannot be changed.';
    case 'not_published':
      return 'Only a published review can be answered.';
  }
  switch (error.kind) {
    case FailureKind.offline:
      return 'You are offline. Nothing was sent. Try again when you are connected.';
    case FailureKind.expired:
      return 'Your session has expired. Sign in again to continue.';
    case FailureKind.rateLimited:
      return 'Too many attempts. Wait a moment, then try again.';
    case FailureKind.notFound:
      return 'This is no longer available.';
    case FailureKind.forbidden:
      return error.message.toLowerCase().contains('verified email')
          ? 'Verify your email address in your profile settings to do this.'
          : 'You do not have access to do this.';
    case FailureKind.conflict:
      return 'This has changed since you opened it. Go back and try again.';
    case FailureKind.invalid:
      return 'Check what you entered and try again.';
    default:
      return 'The service is unavailable right now. Please try again.';
  }
}

bool needsSignIn(Object error) =>
    error is ApiFailure && error.kind == FailureKind.expired;

/// The review or report target a route carries as one string.
class ReviewTarget {
  const ReviewTarget(this.businessId, [this.threadId]);
  final String businessId;
  final String? threadId;

  String get encoded => threadId == null ? businessId : '$businessId/$threadId';

  static ReviewTarget? decode(String? raw) {
    if (raw == null) return null;
    final parts = raw.split('/');
    if (parts.length > 2 || !parts.every(isApiId)) return null;
    return ReviewTarget(parts[0], parts.length == 2 ? parts[1] : null);
  }
}

class ReportTarget {
  const ReportTarget(this.type, this.id);
  final String type;
  final String id;
  String get encoded => '$type:$id';

  static ReportTarget? decode(String? raw) {
    if (raw == null) return null;
    final parts = raw.split(':');
    if (parts.length != 2 ||
        !const {'review', 'review_response', 'inquiry_message'}
            .contains(parts[0]) ||
        !isApiId(parts[1])) {
      return null;
    }
    return ReportTarget(parts[0], parts[1]);
  }
}

String inquiryStateLabel(InquiryState state) => switch (state) {
      InquiryState.open => 'Open',
      InquiryState.closedByCustomer => 'Closed by you',
      InquiryState.closedByBusiness => 'Closed by the business',
      InquiryState.blocked => 'Closed',
    };

String reviewStateLabel(ReviewState state) => switch (state) {
      ReviewState.published => 'Published',
      ReviewState.held => 'Waiting for a check',
      ReviewState.removed => 'Removed',
      ReviewState.withdrawn => 'Withdrawn',
    };

String businessStateLabel(String state) => switch (state) {
      'draft' => 'Draft',
      'submitted' => 'Submitted for review',
      'under_review' => 'Under review',
      'needs_info' => 'More information needed',
      'verified' => 'Verified',
      'rejected' => 'Not approved',
      'suspended' => 'Suspended',
      'revoked' => 'Verification withdrawn',
      'closed' => 'Closed',
      _ => state.replaceAll('_', ' '),
    };

String roleLabel(BusinessRole role) =>
    role == BusinessRole.owner ? 'Owner' : 'Staff';

/// Why a business cannot be listed yet, from the service's reason codes.
String listingReasonLabel(String code) => switch (code) {
      'not_verified' => 'The business is not verified yet.',
      'no_approved_profile' => 'The profile has not been approved yet.',
      _ => code.replaceAll('_', ' '),
    };

/// A reviewer's reason code, shown as the service sent it. The wording of these reasons is not yet approved.
String reasonText(String code) => code.replaceAll('_', ' ');

/// A code the service shows once. It lives only in this widget's memory while the screen is open: it is never
/// written to storage or logged, and "Done" removes it.
class OneTimeCodeCard extends StatelessWidget {
  const OneTimeCodeCard({
    super.key,
    required this.title,
    required this.code,
    required this.expiresAt,
    required this.onCopy,
    required this.onDone,
    this.onRevoke,
  });
  final String title, code;
  final DateTime expiresAt;
  final VoidCallback onCopy, onDone;
  final VoidCallback? onRevoke;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
            color: KoloVibeColors.softBlue,
            borderRadius: BorderRadius.circular(KoloVibeRadii.tile)),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(title, style: KoloVibeText.body(15, weight: FontWeight.w700)),
            const SizedBox(height: 8),
            SelectableText(code,
                key: const ValueKey('one-time-code'),
                style: KoloVibeText.body(18, weight: FontWeight.w700)),
            const SizedBox(height: 8),
            Text(
                'Shown once. KoloVibe cannot show this code again and the app does not keep it. It expires on ${dateLabel(expiresAt)}.',
                style: KoloVibeText.body(12, height: 1.4)),
            const SizedBox(height: 8),
            Wrap(spacing: 8, children: [
              OutlinedButton(onPressed: onCopy, child: const Text('Copy code')),
              if (onRevoke != null)
                TextButton(
                    onPressed: onRevoke,
                    child: const Text('Revoke invitation')),
              TextButton(onPressed: onDone, child: const Text('Done')),
            ]),
          ],
        ),
      );
}

/// Whether a failure means the person no longer has access to a business (it was removed, closed or never theirs).
/// The service answers an unknown business and one the person has no right to the same way, on purpose.
bool accessLost(Object error) =>
    error is ApiFailure &&
    (error.kind == FailureKind.notFound || error.kind == FailureKind.forbidden);

/// The service's single answer to something it will not accept without saying why (404, no reason code).
bool isNotFoundFailure(Object error) =>
    error is ApiFailure &&
    error.kind == FailureKind.notFound &&
    error.code == null;
