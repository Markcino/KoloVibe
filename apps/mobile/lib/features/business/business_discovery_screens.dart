import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../app/screen_route.dart';
import '../../core/presentation/design_node.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/kolo_components.dart';
import '../../shared/widgets/live_state_view.dart';
import 'business_lists.dart';
import 'business_models.dart';
import 'business_page.dart';
import 'business_screens.dart';
import 'business_ui.dart';
import 'live_business_repository.dart';

// ---- M-109 Businesses home ----------------------------------------------------------------------------------------

class BusinessHomeScreen extends StatefulWidget {
  const BusinessHomeScreen(
      {super.key, required this.repository, required this.catalog});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  @override
  State<BusinessHomeScreen> createState() => _BusinessHomeScreenState();
}

class _BusinessHomeScreenState extends State<BusinessHomeScreen> {
  final _search = TextEditingController();

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  void _go(BusinessFilters filters) =>
      openBusiness(context, BusinessScreens.results,
          entityId: filters.encode());

  void _submit() {
    final words = _search.text.trim();
    _go(BusinessFilters(query: words.isEmpty ? null : words));
  }

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.home,
        catalog: widget.catalog,
        title: 'Businesses',
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            KoloTextField(
              label: 'Search businesses',
              controller: _search,
              hint: 'Name, product or service',
              maxLength: 100,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => _submit(),
            ),
            const SizedBox(height: 4),
            Align(
              alignment: Alignment.centerRight,
              child: KoloPillButton(label: 'Search', onPressed: _submit),
            ),
            const SizedBox(height: 20),
            KoloSectionHeading(
              title: 'Categories',
              actionLabel: 'See all',
              onAction: () => openBusiness(context, BusinessScreens.categories),
            ),
            const SizedBox(height: 8),
            BusinessLoader<List<BusinessCategory>>(
              inline: true,
              load: widget.repository.categories,
              builder: (context, categories, reload) {
                final roots = categories.where((c) => c.parent == null);
                if (roots.isEmpty) {
                  return const KoloInlineState(
                      title: 'No categories yet',
                      message: 'Categories will appear here once added.');
                }
                return Wrap(spacing: 8, runSpacing: 8, children: [
                  for (final category in roots.take(8))
                    KoloChip(
                        label: category.name,
                        onTap: () =>
                            _go(BusinessFilters(category: category.slug))),
                ]);
              },
            ),
            const SizedBox(height: 24),
            KoloSectionHeading(
              title: 'Businesses',
              actionLabel: 'See all',
              onAction: () => _go(const BusinessFilters()),
            ),
            const SizedBox(height: 8),
            BusinessLoader<ResultPage<BusinessCard>>(
              inline: true,
              load: () => widget.repository.search(),
              builder: (context, page, reload) {
                if (page.items.isEmpty) {
                  return const KoloInlineState(
                      title: 'No businesses yet',
                      message:
                          'Businesses appear here once they are verified and published.');
                }
                return Column(children: [
                  for (final card in page.items.take(5))
                    BusinessCardTile(
                        card: card,
                        onTap: () => openBusiness(
                            context, BusinessScreens.detail,
                            entityId: card.id)),
                ]);
              },
            ),
            const SizedBox(height: 16),
            const KoloSectionHeading(title: 'Your activity'),
            KoloListRow(
                title: 'My questions to businesses',
                onTap: () =>
                    openBusiness(context, BusinessScreens.myInquiries)),
            KoloListRow(
                title: 'My reviews',
                onTap: () => openBusiness(context, BusinessScreens.myReviews)),
            KoloListRow(
                title: 'My businesses',
                subtitle: 'Manage a business you own or work for',
                onTap: () =>
                    openBusiness(context, BusinessScreens.myBusinesses)),
            KoloListRow(
                title: 'Join a business team',
                subtitle: 'Use an invitation code from a business owner',
                onTap: () => openBusiness(context, BusinessScreens.redeem)),
            KoloListRow(
                title: 'What you can see here',
                divider: false,
                onTap: () => openBusiness(context, BusinessScreens.privacy)),
          ],
        ),
      );
}

// ---- M-110 Categories ---------------------------------------------------------------------------------------------

class BusinessCategoriesScreen extends StatelessWidget {
  const BusinessCategoriesScreen(
      {super.key, required this.repository, required this.catalog});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.categories,
        catalog: catalog,
        title: 'Categories',
        scroll: false,
        child: BusinessLoader<List<BusinessCategory>>(
          load: repository.categories,
          builder: (context, categories, reload) {
            void open(String? slug) =>
                openBusiness(context, BusinessScreens.results,
                    entityId: BusinessFilters(category: slug).encode());
            final roots = categories.where((c) => c.parent == null).toList();
            if (roots.isEmpty) {
              return const LiveStateView.empty(
                  title: 'No categories yet',
                  message: 'Categories will appear here once added.',
                  icon: Icons.category_outlined);
            }
            return ListView(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
              children: [
                KoloListRow(title: 'All businesses', onTap: () => open(null)),
                for (final root in roots) ...[
                  KoloListRow(title: root.name, onTap: () => open(root.slug)),
                  for (final child
                      in categories.where((c) => c.parent == root.slug))
                    Padding(
                      padding: const EdgeInsets.only(left: 20),
                      child: KoloListRow(
                          title: child.name, onTap: () => open(child.slug)),
                    ),
                ],
              ],
            );
          },
        ),
      );
}

// ---- M-111 Results ------------------------------------------------------------------------------------------------

class BusinessResultsScreen extends StatefulWidget {
  const BusinessResultsScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      this.encodedFilters});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final String? encodedFilters;
  @override
  State<BusinessResultsScreen> createState() => _BusinessResultsScreenState();
}

class _BusinessResultsScreenState extends State<BusinessResultsScreen> {
  late BusinessFilters _filters = BusinessFilters.decode(widget.encodedFilters);
  late final _search = TextEditingController(text: _filters.query ?? '');

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  void _apply(BusinessFilters next) => setState(() {
        _filters = next;
        _search.text = next.query ?? '';
      });

  Future<void> _openFilters() async {
    final route =
        ScreenRoute(BusinessScreens.filters, entityId: _filters.encode());
    final result = await Navigator.of(context)
        .pushNamed<BusinessFilters>(route.name, arguments: route);
    if (result != null && mounted) _apply(result);
  }

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.results,
        catalog: widget.catalog,
        title: 'Find a business',
        scroll: false,
        child: BusinessPagedList<BusinessCard>(
          key: ValueKey(_filters.encode()),
          fetch: (cursor) => widget.repository.search(
              query: _filters.query,
              category: _filters.category,
              county: _filters.county,
              openNow: _filters.openNow,
              verifiedOnly: _filters.verifiedOnly,
              cursor: cursor),
          header: _header(),
          itemBuilder: (context, card) => BusinessCardTile(
              card: card,
              onTap: () => openBusiness(context, BusinessScreens.detail,
                  entityId: card.id)),
          empty: KoloInlineState(
            title: 'No businesses found',
            message: _filters.isEmpty
                ? 'No business is listed yet.'
                : 'Try different words or fewer filters.',
            icon: Icons.search_off,
            actionLabel: _filters.isEmpty ? null : 'Clear search and filters',
            onAction:
                _filters.isEmpty ? null : () => _apply(const BusinessFilters()),
          ),
        ),
      );

  Widget _header() => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          KoloTextField(
            label: 'Search businesses',
            controller: _search,
            maxLength: 100,
            textInputAction: TextInputAction.search,
            onSubmitted: (value) => _apply(_filters.copyWith(
                query: value.trim().isEmpty ? null : value.trim())),
          ),
          Wrap(spacing: 8, runSpacing: 8, children: [
            KoloPillButton(
                label: _filters.active == 0
                    ? 'Filters'
                    : 'Filters (${_filters.active})',
                onPressed: _openFilters),
            if (!_filters.isEmpty)
              KoloPillButton(
                  label: 'Clear',
                  onPressed: () => _apply(const BusinessFilters())),
          ]),
          const SizedBox(height: 12),
        ],
      );
}

// ---- M-112 Filters ------------------------------------------------------------------------------------------------

class BusinessFiltersScreen extends StatefulWidget {
  const BusinessFiltersScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      this.encodedFilters});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final String? encodedFilters;
  @override
  State<BusinessFiltersScreen> createState() => _BusinessFiltersScreenState();
}

class _BusinessFiltersScreenState extends State<BusinessFiltersScreen> {
  late BusinessFilters _filters = BusinessFilters.decode(widget.encodedFilters);

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.filters,
        catalog: widget.catalog,
        title: 'Filters',
        showNavigation: false,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            BusinessLoader<List<BusinessCategory>>(
              inline: true,
              load: widget.repository.categories,
              builder: (context, categories, reload) =>
                  DropdownButtonFormField<String?>(
                key: const ValueKey('filter-category'),
                initialValue: categories.any((c) => c.slug == _filters.category)
                    ? _filters.category
                    : null,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Category'),
                items: [
                  const DropdownMenuItem(value: null, child: Text('Any')),
                  for (final category in categories)
                    DropdownMenuItem(
                        value: category.slug, child: Text(category.name)),
                ],
                onChanged: (value) => setState(
                    () => _filters = _filters.copyWith(category: value)),
              ),
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<String?>(
              key: const ValueKey('filter-county'),
              initialValue: _filters.county,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'County'),
              items: [
                const DropdownMenuItem(value: null, child: Text('Any')),
                for (final county in counties)
                  DropdownMenuItem(
                      value: county.code, child: Text(county.label)),
              ],
              onChanged: (value) =>
                  setState(() => _filters = _filters.copyWith(county: value)),
            ),
            SwitchListTile(
              key: const ValueKey('filter-open'),
              contentPadding: EdgeInsets.zero,
              title: const Text('Open now'),
              subtitle: const Text(
                  'Only businesses that have published their opening hours'),
              value: _filters.openNow,
              onChanged: (value) =>
                  setState(() => _filters = _filters.copyWith(openNow: value)),
            ),
            SwitchListTile(
              key: const ValueKey('filter-verified'),
              contentPadding: EdgeInsets.zero,
              title: const Text('Verified only'),
              value: _filters.verifiedOnly,
              onChanged: (value) => setState(
                  () => _filters = _filters.copyWith(verifiedOnly: value)),
            ),
            const SizedBox(height: 16),
            FilledButton(
                onPressed: () => Navigator.of(context).pop(_filters),
                child: const Text('Show results')),
            TextButton(
                onPressed: () => setState(
                    () => _filters = BusinessFilters(query: _filters.query)),
                child: const Text('Reset filters')),
          ],
        ),
      );
}

// ---- M-113 Detail -------------------------------------------------------------------------------------------------

class BusinessDetailScreen extends StatelessWidget {
  const BusinessDetailScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.businessId});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final String businessId;

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.detail,
        catalog: catalog,
        title: 'Business',
        scroll: false,
        child: BusinessLoader<BusinessDetail>(
          onSignIn: () => signInForBusiness(context, BusinessScreens.detail),
          load: () => repository.detail(businessId),
          builder: (context, detail, reload) => _body(context, detail),
        ),
      );

  Widget _body(BuildContext context, BusinessDetail detail) {
    final card = detail.card;
    final place = [
      if (detail.addressLine != null) detail.addressLine!,
      card.city,
      countyLabel(card.countyCode),
    ].where((part) => part.isNotEmpty).join(', ');
    void open(int screen) => openBusiness(context, screen, entityId: card.id);
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
      children: [
        KoloHeadline(card.name, size: 24),
        const SizedBox(height: 8),
        Wrap(spacing: 8, runSpacing: 8, children: [
          if (card.verified) const KoloBadge('Verified', filled: true),
          KoloBadge(card.category.name),
          KoloBadge(openLabel(card.openNow)),
        ]),
        const SizedBox(height: 12),
        Text(ratingLabel(detail.rating),
            style: KoloVibeText.body(14, weight: FontWeight.w600)),
        if (place.isNotEmpty) ...[
          const SizedBox(height: 4),
          Text(place, style: KoloVibeText.body(13)),
        ],
        if (detail.description.isNotEmpty) ...[
          const SizedBox(height: 16),
          Text(detail.description, style: KoloVibeText.body(14, height: 1.5)),
        ],
        const SizedBox(height: 16),
        KoloListRow(
            title: 'Opening hours',
            subtitle: openLabel(card.openNow),
            onTap: () => open(BusinessScreens.hours)),
        KoloListRow(
            title: 'Contact details',
            onTap: () => open(BusinessScreens.contact)),
        KoloListRow(
            title: 'Reviews',
            subtitle: ratingLabel(detail.rating),
            onTap: () => open(BusinessScreens.reviews)),
        const SizedBox(height: 16),
        FilledButton(
            onPressed: () => open(BusinessScreens.ask),
            child: const Text('Ask a question')),
        const SizedBox(height: 8),
        OutlinedButton(
            onPressed: () => open(BusinessScreens.writeReview),
            child: const Text('Write a review')),
      ],
    );
  }
}

// ---- M-114 Hours --------------------------------------------------------------------------------------------------

class BusinessHoursScreen extends StatelessWidget {
  const BusinessHoursScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.businessId});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final String businessId;

  static String _range(HoursRule rule) => '${rule.opens} – ${rule.closes}';

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.hours,
        catalog: catalog,
        title: 'Opening hours',
        child: BusinessLoader<BusinessDetail>(
          load: () => repository.detailCached(businessId),
          builder: (context, detail, reload) {
            final hours = detail.hours;
            if (hours.isEmpty) {
              return const KoloInlineState(
                title: 'Opening hours not published',
                message:
                    'This business has not published its opening hours, so KoloVibe cannot say whether it is open.',
                icon: Icons.schedule,
              );
            }
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(openLabel(detail.card.openNow),
                    style: KoloVibeText.body(16, weight: FontWeight.w700)),
                const SizedBox(height: 4),
                Text('Times are in ${detail.timeZone}.',
                    style: KoloVibeText.body(12)),
                const SizedBox(height: 12),
                for (var day = 0; day < 7; day++)
                  KoloListRow(
                    title: weekdays[day],
                    subtitle: () {
                      final rules =
                          hours.rules.where((r) => r.weekday == day).toList();
                      return rules.isEmpty
                          ? 'Closed'
                          : rules.map(_range).join(', ');
                    }(),
                    icon: Icons.schedule,
                  ),
                if (hours.exceptions.isNotEmpty) ...[
                  const SizedBox(height: 16),
                  const KoloSectionHeading(title: 'Special days'),
                  for (final day in hours.exceptions)
                    KoloListRow(
                      title: day.onDate,
                      subtitle: day.closed
                          ? 'Closed'
                          : '${day.opens} – ${day.closes}',
                      icon: Icons.event,
                    ),
                ],
              ],
            );
          },
        ),
      );
}

// ---- M-115 Contact ------------------------------------------------------------------------------------------------

class BusinessContactScreen extends StatelessWidget {
  const BusinessContactScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.businessId});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final String businessId;

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.contact,
        catalog: catalog,
        title: 'Contact details',
        child: BusinessLoader<BusinessDetail>(
          load: () => repository.detailCached(businessId),
          builder: (context, detail, reload) => _content(context, detail),
        ),
      );

  Widget _content(BuildContext context, BusinessDetail detail) {
    switch (detail.access) {
      case ContactAccess.signInRequired:
        return KoloInlineState(
          title: 'Sign in to see contact details',
          message:
              'Contact details are shown to signed-in people with a verified email address.',
          icon: Icons.lock_outline,
          actionLabel: 'Sign in',
          onAction: () => signInForBusiness(context, BusinessScreens.contact),
        );
      case ContactAccess.verifiedEmailRequired:
        return KoloInlineState(
          title: 'Verify your email to see contact details',
          message:
              'Contact details are shown only to people with a verified email address. Check your profile settings.',
          icon: Icons.mark_email_unread_outlined,
          actionLabel: 'Open my profile',
          onAction: () => openBusiness(context, 79),
        );
      case ContactAccess.limitReached:
        return const KoloInlineState(
          title: 'Contact limit reached',
          message:
              'You have reached the limit for viewing contact details for now. Please try again later.',
          icon: Icons.hourglass_empty,
        );
      case ContactAccess.none:
      case ContactAccess.available:
        final contacts = detail.contacts ?? const <ContactValue>[];
        if (contacts.isEmpty) {
          return const KoloInlineState(
            title: 'No public contact details',
            message: 'This business has not made any contact details public.',
            icon: Icons.contact_phone_outlined,
          );
        }
        return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              for (final contact in contacts)
                KoloListRow(
                  title: contact.value,
                  subtitle: labelFor(contactKinds, contact.kind),
                  icon: Icons.copy,
                  onTap: () async {
                    await Clipboard.setData(ClipboardData(text: contact.value));
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('Copied')));
                    }
                  },
                ),
              const SizedBox(height: 12),
              const KoloNote(
                  title: 'Tap a detail to copy it',
                  message:
                      'KoloVibe does not open calls, emails or links for you.'),
            ]);
    }
  }
}

// ---- M-116 Reviews ------------------------------------------------------------------------------------------------

class BusinessReviewsScreen extends StatelessWidget {
  const BusinessReviewsScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.businessId});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final String businessId;

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.reviews,
        catalog: catalog,
        title: 'Reviews',
        scroll: false,
        child: BusinessPagedList<PublicReview>(
          fetch: (cursor) => repository.reviews(businessId, cursor: cursor),
          empty: const KoloInlineState(
              title: 'No reviews yet',
              message: 'Be the first to share how it went.',
              icon: Icons.rate_review_outlined),
          itemBuilder: (context, review) => _ReviewTile(review: review),
        ),
      );
}

class _ReviewTile extends StatelessWidget {
  const _ReviewTile({required this.review});
  final PublicReview review;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: DecoratedBox(
          decoration: BoxDecoration(
              color: Colors.white,
              border: Border.all(color: KoloVibeColors.line),
              borderRadius: BorderRadius.circular(KoloVibeRadii.tile)),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Semantics(
                  label: 'Rating ${starsLabel(review.rating)}',
                  excludeSemantics: true,
                  child: Text(
                      '${'★' * review.rating}${'☆' * (5 - review.rating)}',
                      style: KoloVibeText.body(18, color: KoloVibeColors.gold)),
                ),
                if (review.title != null) ...[
                  const SizedBox(height: 4),
                  Text(review.title!,
                      style: KoloVibeText.body(15, weight: FontWeight.w700)),
                ],
                const SizedBox(height: 4),
                Text(review.body, style: KoloVibeText.body(14, height: 1.4)),
                const SizedBox(height: 8),
                Text(
                    '${review.authorLabel} · ${dateLabel(review.createdAt)}'
                    '${review.editedAt == null ? '' : ' · edited'}'
                    ' · ${reviewBasisLabel(review.basis)}',
                    style: KoloVibeText.body(12)),
                if (review.response != null) ...[
                  const SizedBox(height: 12),
                  KoloNote(
                      title:
                          'Reply from the business · ${dateLabel(review.response!.createdAt)}',
                      message: review.response!.body,
                      icon: Icons.reply),
                ],
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    onPressed: () => openBusiness(
                        context, BusinessScreens.report,
                        entityId: 'review:${review.id}'),
                    child: const Text('Report this review'),
                  ),
                ),
              ],
            ),
          ),
        ),
      );
}

// ---- M-117 What you can see ---------------------------------------------------------------------------------------

class BusinessPrivacyScreen extends StatelessWidget {
  const BusinessPrivacyScreen({super.key, required this.catalog});
  final DesignCatalog catalog;

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.privacy,
        catalog: catalog,
        title: 'What you can see here',
        child: const Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            KoloNote(
                title: 'Only what a business chooses to publish',
                message:
                    'A listing shows the name, category, place, description, opening hours and the contact details the business marked public. Exact map coordinates are never shown.',
                icon: Icons.storefront_outlined),
            SizedBox(height: 12),
            KoloNote(
                title: 'Contact details',
                message:
                    'Contact details are shown to signed-in people with a verified email address, and viewing them is limited. KoloVibe never opens calls, emails or links for you.',
                icon: Icons.contact_phone_outlined),
            SizedBox(height: 12),
            KoloNote(
                title: 'Reviews',
                message:
                    'Reviews show a label such as “Reviewer 3”, not a name or email address. Each review says how it was written: interaction confirmed, invited by the business, or open.',
                icon: Icons.rate_review_outlined),
            SizedBox(height: 12),
            KoloNote(
                title: 'Verified',
                message:
                    'A “Verified” mark means KoloVibe reviewed the business. It is set by KoloVibe, never by the business.',
                icon: Icons.verified_outlined),
            SizedBox(height: 12),
            KoloNote(
                title: 'Your questions and reviews',
                message:
                    'A question you send is seen only by you and the business. Everything is shown as plain text.',
                icon: Icons.lock_outline),
          ],
        ),
      );
}
