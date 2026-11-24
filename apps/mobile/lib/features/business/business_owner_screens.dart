import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import '../../core/presentation/design_node.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/kolo_components.dart';
import '../system/system_ui.dart';
import 'business_access.dart';
import 'business_context.dart';
import 'business_lists.dart';
import 'business_models.dart';
import 'business_page.dart';
import 'business_screens.dart';
import 'business_ui.dart';
import 'live_business_repository.dart';

void _go(BuildContext context, int screen, {String? entityId}) =>
    openBusiness(context, screen, entityId: entityId);

void _signIn(BuildContext context, int returnTo) =>
    openBusiness(context, 4, returnTo: returnTo);

/// A failed send, with a sign-in button when the session ended.
class SendError extends StatelessWidget {
  const SendError(
      {super.key,
      required this.error,
      required this.returnTo,
      this.title = 'Not saved'});
  final Object error;
  final int returnTo;
  final String title;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: KoloInlineState(
          title: title,
          message: failureText(error),
          icon: Icons.error_outline,
          actionLabel: needsSignIn(error) ? 'Sign in' : null,
          onAction:
              needsSignIn(error) ? () => _signIn(context, returnTo) : null,
        ),
      );
}

Widget _problem(String text) => Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child:
          Text(text, style: KoloVibeText.body(13, color: KoloVibeColors.red)),
    );

// ---- M-126 My businesses ------------------------------------------------------------------------------------------

class BusinessMyBusinessesScreen extends StatelessWidget {
  const BusinessMyBusinessesScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.context});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final BusinessContext? context;

  /// Remembers the choice (for the switcher) and opens the screen that fits the person's role.
  Future<void> open(BuildContext screen, MyBusiness business) async {
    final account = repository.account.signedInAccountId;
    if (account != null) await context?.select(account, business.id);
    if (!screen.mounted) return;
    _go(screen,
        business.isOwner ? BusinessScreens.manage : BusinessScreens.staffHome,
        entityId: business.id);
  }

  @override
  Widget build(BuildContext screen) => BusinessPage(
        screen: BusinessScreens.myBusinesses,
        catalog: catalog,
        title: 'My businesses',
        scroll: false,
        child: BusinessPagedList<MyBusiness>(
          onSignIn: () => _signIn(screen, BusinessScreens.myBusinesses),
          fetch: (cursor) => repository.myBusinesses(cursor: cursor),
          header: Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Wrap(spacing: 8, runSpacing: 8, children: [
              KoloPillButton(
                  label: 'Register a business',
                  onPressed: () => _go(screen, BusinessScreens.register)),
              KoloPillButton(
                  label: 'Join a business team',
                  onPressed: () => _go(screen, BusinessScreens.redeem)),
            ]),
          ),
          empty: const KoloInlineState(
            title: 'No businesses yet',
            message:
                'Register a business you own, or join a team with an invitation code.',
            icon: Icons.storefront_outlined,
          ),
          itemBuilder: (context, business) => KoloListRow(
            title: business.name,
            subtitle:
                '${roleLabel(business.role)} · ${businessStateLabel(business.state)}',
            onTap: () => open(context, business),
          ),
        ),
      );
}

// ---- M-127 Register -----------------------------------------------------------------------------------------------

class BusinessRegisterScreen extends StatefulWidget {
  const BusinessRegisterScreen(
      {super.key, required this.repository, required this.catalog});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  @override
  State<BusinessRegisterScreen> createState() => _BusinessRegisterScreenState();
}

class _BusinessRegisterScreenState extends State<BusinessRegisterScreen> {
  final _name = TextEditingController();
  final _legal = TextEditingController();
  final _attempt = AttemptKey();
  bool _busy = false, _done = false;
  Object? _error;
  String? _problemText;

  @override
  void dispose() {
    _name.dispose();
    _legal.dispose();
    super.dispose();
  }

  bool get _invitationRequired =>
      _error is ApiFailure &&
      (_error as ApiFailure).code == 'invitation_required';

  Future<void> _submit() async {
    if (_busy) return;
    final name = _name.text.trim(), legal = _legal.text.trim();
    if (name.length < 2 || legal.length < 2) {
      setState(() => _problemText =
          'Enter the name customers know and the registered legal name.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _problemText = null;
    });
    try {
      final created = await widget.repository.register(
          displayName: name,
          legalName: legal,
          key: _attempt.forContent('$name|$legal'));
      _attempt.reset();
      if (!mounted) return;
      _done = true;
      notifySuccess(context, 'Business registered');
      final route = ScreenRoute(BusinessScreens.manage, entityId: created.id);
      Navigator.of(context).pushReplacementNamed(route.name, arguments: route);
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => UnsavedChangesGuard(
        dirty: !_done &&
            (_name.text.trim().isNotEmpty || _legal.text.trim().isNotEmpty),
        busy: _busy,
        child: BusinessPage(
          screen: BusinessScreens.register,
          catalog: widget.catalog,
          title: 'Register a business',
          showNavigation: false,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const KoloNote(
                  title: 'Registration is by invitation',
                  message:
                      'During the pilot only invited accounts can register a business. If yours has not been invited, registering will be refused.',
                  icon: Icons.mail_outline),
              const SizedBox(height: 16),
              KoloTextField(
                  label: 'Business name',
                  controller: _name,
                  maxLength: 80,
                  readOnly: _busy,
                  helper: 'The name customers see.',
                  onChanged: (_) => setState(() {})),
              KoloTextField(
                  label: 'Registered legal name',
                  controller: _legal,
                  maxLength: 160,
                  readOnly: _busy,
                  helper:
                      'Only you and KoloVibe reviewers see this. It is never shown to customers.',
                  onChanged: (_) => setState(() {})),
              if (_problemText != null) _problem(_problemText!),
              if (_error != null)
                _invitationRequired
                    ? const KoloNote(
                        key: ValueKey('invitation-required'),
                        title: 'Invitation required',
                        message:
                            'Registering a business is by invitation only during the pilot, and your account has not been invited. There is nothing more to do here yet.',
                        icon: Icons.lock_outline)
                    : SendError(
                        error: _error!,
                        returnTo: BusinessScreens.register,
                        title: 'Not registered'),
              const SizedBox(height: 8),
              FilledButton(
                  onPressed: _busy ? null : _submit,
                  child: Text(_busy ? 'Registering…' : 'Register business')),
            ],
          ),
        ),
      );
}

// ---- M-128 Manage home --------------------------------------------------------------------------------------------

/// What a business home shows: the business and, for owners, its listing. Used by the owner (M-128) and by staff
/// (M-144), which show different rows from the same data.
typedef HomeData = ({MyBusiness business, ListingStatus? listing});

Future<HomeData> loadHome(
    LiveBusinessRepository repository, String businessId) async {
  final business = await repository.business(businessId);
  // The listing is owner information; staff never ask for it.
  final listing =
      business.isOwner ? await repository.listingStatus(businessId) : null;
  return (business: business, listing: listing);
}

class BusinessManageScreen extends StatelessWidget {
  const BusinessManageScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.businessId,
      this.businessContext,
      this.screen = BusinessScreens.manage,
      this.title = 'Manage business'});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final String businessId;
  final BusinessContext? businessContext;
  final int screen;
  final String title;

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: screen,
        catalog: catalog,
        title: title,
        child: BusinessLoader<HomeData>(
          onSignIn: () => _signIn(context, BusinessScreens.myBusinesses),
          load: () async {
            try {
              return await loadHome(repository, businessId);
            } catch (error) {
              // Access that is gone is not "something went wrong": forget the choice and say so.
              if (accessLost(error) &&
                  businessContext?.businessId == businessId) {
                await businessContext?.clear();
              }
              rethrow;
            }
          },
          errorBuilder: (context, error) =>
              accessLost(error) ? const AccessRemovedBody() : null,
          builder: (context, data, reload) => BusinessHomeBody(data: data),
        ),
      );
}

class BusinessHomeBody extends StatelessWidget {
  const BusinessHomeBody({super.key, required this.data});
  final HomeData data;

  @override
  Widget build(BuildContext context) {
    final business = data.business;
    final id = business.id;
    final owner = business.isOwner;
    void open(int screen) => _go(context, screen, entityId: id);
    final listing = data.listing;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        KoloHeadline(business.name, size: 24),
        const SizedBox(height: 8),
        Wrap(spacing: 8, runSpacing: 8, children: [
          KoloBadge(roleLabel(business.role)),
          KoloBadge(businessStateLabel(business.state)),
          if (business.verified) const KoloBadge('Verified', filled: true),
          if (listing != null)
            KoloBadge(listing.listed ? 'Listed publicly' : 'Not listed'),
        ]),
        const SizedBox(height: 16),
        KoloListRow(
            title: 'Inbox',
            subtitle: 'Questions from customers',
            onTap: () => open(BusinessScreens.inbox)),
        KoloListRow(
            title: 'Opening hours',
            onTap: () => open(BusinessScreens.editHours)),
        if (owner) ...[
          KoloListRow(
              title: 'Business details',
              subtitle: 'Name, category, place and description',
              onTap: () => open(BusinessScreens.editProfile)),
          KoloListRow(
              title: 'Contact details',
              onTap: () => open(BusinessScreens.editContacts)),
          KoloListRow(
              title: 'Profile review',
              subtitle: 'What is public and what is waiting',
              onTap: () => open(BusinessScreens.profileStatus)),
          KoloListRow(
              title: 'Verification',
              onTap: () => open(BusinessScreens.verification)),
          KoloListRow(
              title: 'Listing',
              subtitle: 'Show or hide in search',
              onTap: () => open(BusinessScreens.listing)),
          KoloListRow(
              title: 'Reviews and replies',
              onTap: () => open(BusinessScreens.ownerReviews)),
          KoloListRow(
              title: 'Review invitations',
              onTap: () => open(BusinessScreens.reviewInvitations)),
          KoloListRow(
              title: 'Team',
              subtitle: 'Staff and invitations',
              onTap: () => open(BusinessScreens.team)),
        ] else
          KoloListRow(
              title: 'Leave this business',
              destructive: true,
              onTap: () => open(BusinessScreens.leave)),
        KoloListRow(
            title: 'Switch business',
            onTap: () => _go(context, BusinessScreens.switcher)),
        KoloListRow(
            title: 'My businesses',
            divider: false,
            onTap: () => _go(context, BusinessScreens.myBusinesses)),
      ],
    );
  }
}

// ---- M-129 Business details ---------------------------------------------------------------------------------------

class BusinessEditProfileScreen extends StatelessWidget {
  const BusinessEditProfileScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.businessId});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final String businessId;

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.editProfile,
        catalog: catalog,
        title: 'Business details',
        showNavigation: false,
        child: BusinessLoader<(BusinessProfile, List<BusinessCategory>)>(
          onSignIn: () => _signIn(context, BusinessScreens.myBusinesses),
          load: () async => (
            await repository.profile(businessId),
            await repository.categories()
          ),
          builder: (context, data, reload) => _ProfileForm(
              repository: repository,
              businessId: businessId,
              profile: data.$1,
              categories: data.$2),
        ),
      );
}

class _ProfileForm extends StatefulWidget {
  const _ProfileForm(
      {required this.repository,
      required this.businessId,
      required this.profile,
      required this.categories});
  final LiveBusinessRepository repository;
  final String businessId;
  final BusinessProfile profile;
  final List<BusinessCategory> categories;
  @override
  State<_ProfileForm> createState() => _ProfileFormState();
}

class _ProfileFormState extends State<_ProfileForm> {
  late final ProfileRevision? _base =
      widget.profile.working ?? widget.profile.approved;
  late final _name = TextEditingController(text: _base?.name ?? '');
  late final _description =
      TextEditingController(text: _base?.description ?? '');
  late final _city = TextEditingController(text: _base?.city ?? '');
  late final _address = TextEditingController(text: _base?.addressLine ?? '');
  final _attempt = AttemptKey();
  late String? _category =
      widget.categories.any((c) => c.slug == _base?.category)
          ? _base?.category
          : null;
  late String? _county = counties.any((c) => c.code == _base?.countyCode)
      ? _base?.countyCode
      : null;
  late bool _addressPublic = _base?.addressPublic ?? false;
  bool _busy = false, _saved = false;
  Object? _error;
  String? _problemText;

  @override
  void dispose() {
    _name.dispose();
    _description.dispose();
    _city.dispose();
    _address.dispose();
    super.dispose();
  }

  bool get _changed =>
      _name.text.trim() != (_base?.name ?? '') ||
      _description.text.trim() != (_base?.description ?? '') ||
      _city.text.trim() != (_base?.city ?? '') ||
      _address.text.trim() != (_base?.addressLine ?? '') ||
      _category != _base?.category ||
      _county !=
          (counties.any((c) => c.code == _base?.countyCode)
              ? _base?.countyCode
              : null) ||
      _addressPublic != (_base?.addressPublic ?? false);

  Future<void> _save() async {
    if (_busy) return;
    final name = _name.text.trim(), city = _city.text.trim();
    if (name.length < 2) {
      setState(() =>
          _problemText = 'The business name needs at least 2 characters.');
      return;
    }
    if (city.isEmpty && _city.text.trim() != (_base?.city ?? '')) {
      setState(() => _problemText = 'Enter the city or town.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _problemText = null;
    });
    final b = _base;
    try {
      await widget.repository.editProfile(widget.businessId,
          displayName: name == b?.name ? null : name,
          category: _category == b?.category ? null : _category,
          description: _description.text.trim() == (b?.description ?? '')
              ? null
              : _description.text.trim(),
          countyCode: _county == b?.countyCode ? null : _county,
          city: city == (b?.city ?? '') ? null : city,
          addressLine: _address.text.trim() == (b?.addressLine ?? '')
              ? null
              : _address.text.trim(),
          addressPublic: _addressPublic == (b?.addressPublic ?? false)
              ? null
              : _addressPublic,
          key: _attempt.forContent(
              '$name|$_category|${_description.text.trim()}|$_county|$city|${_address.text.trim()}|$_addressPublic'));
      _attempt.reset();
      if (!mounted) return;
      setState(() => _saved = true);
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => UnsavedChangesGuard(
        dirty: !_saved && _changed,
        busy: _busy,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const KoloNote(
                title: 'Changes are checked before they go live',
                message:
                    'Saving keeps a draft. Submit it from Profile review. Until a change is approved, the current public profile stays as it is.',
                icon: Icons.rule_folder_outlined),
            const SizedBox(height: 16),
            KoloTextField(
                label: 'Business name',
                controller: _name,
                maxLength: 80,
                readOnly: _busy,
                onChanged: (_) => setState(() {})),
            DropdownButtonFormField<String?>(
              key: const ValueKey('profile-category'),
              initialValue: _category,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Category'),
              items: [
                for (final category in widget.categories)
                  DropdownMenuItem(
                      value: category.slug, child: Text(category.name)),
              ],
              onChanged: _busy ? null : (v) => setState(() => _category = v),
            ),
            const SizedBox(height: 16),
            KoloTextField(
                label: 'Description',
                controller: _description,
                maxLength: 2000,
                maxLines: 5,
                readOnly: _busy,
                onChanged: (_) => setState(() {})),
            DropdownButtonFormField<String?>(
              key: const ValueKey('profile-county'),
              initialValue: _county,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'County'),
              items: [
                for (final county in counties)
                  DropdownMenuItem(
                      value: county.code, child: Text(county.label)),
              ],
              onChanged: _busy ? null : (v) => setState(() => _county = v),
            ),
            const SizedBox(height: 16),
            KoloTextField(
                label: 'City or town',
                controller: _city,
                maxLength: 80,
                readOnly: _busy,
                onChanged: (_) => setState(() {})),
            KoloTextField(
                label: 'Address (optional)',
                controller: _address,
                maxLength: 200,
                readOnly: _busy,
                onChanged: (_) => setState(() {})),
            SwitchListTile(
              key: const ValueKey('profile-address-public'),
              contentPadding: EdgeInsets.zero,
              title: const Text('Show the address publicly'),
              subtitle: const Text(
                  'Exact map coordinates are never shown or collected.'),
              value: _addressPublic,
              onChanged:
                  _busy ? null : (v) => setState(() => _addressPublic = v),
            ),
            if (_problemText != null) _problem(_problemText!),
            if (_error != null)
              SendError(error: _error!, returnTo: BusinessScreens.myBusinesses),
            if (_saved)
              const Padding(
                padding: EdgeInsets.only(bottom: 12),
                child: KoloNote(
                    key: ValueKey('profile-saved'),
                    title: 'Saved as a draft',
                    message: 'Open Profile review to submit it for checking.',
                    tone: KoloNoteTone.success,
                    icon: Icons.check_circle_outline),
              ),
            FilledButton(
                onPressed: _busy || !_changed ? null : _save,
                child: Text(_busy ? 'Saving…' : 'Save draft')),
            if (_saved)
              TextButton(
                  onPressed: () => _go(context, BusinessScreens.profileStatus,
                      entityId: widget.businessId),
                  child: const Text('Go to Profile review')),
          ],
        ),
      );
}

// ---- M-130 Contact details ----------------------------------------------------------------------------------------

class BusinessEditContactsScreen extends StatelessWidget {
  const BusinessEditContactsScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.businessId});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final String businessId;

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.editContacts,
        catalog: catalog,
        title: 'Contact details',
        showNavigation: false,
        child: BusinessLoader<BusinessProfile>(
          onSignIn: () => _signIn(context, BusinessScreens.myBusinesses),
          load: () => repository.profile(businessId),
          builder: (context, profile, reload) => profile.approved != null
              ? _LiveContacts(
                  contacts: (profile.working ?? profile.approved)!.contacts)
              : _ContactsForm(
                  repository: repository,
                  businessId: businessId,
                  initial: profile.working?.contacts ?? const []),
        ),
      );
}

/// Contact details on a live profile cannot be changed yet (the extra security check does not exist), so the editor
/// is not shown: one explanatory row and the current values.
class _LiveContacts extends StatelessWidget {
  const _LiveContacts({required this.contacts});
  final List<ProfileContact> contacts;

  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const KoloNote(
              key: ValueKey('contacts-locked'),
              title: 'Contact details cannot be changed yet',
              message:
                  'Changing contact details on a live profile needs an extra security check that is not available yet.',
              icon: Icons.lock_outline),
          const SizedBox(height: 12),
          if (contacts.isEmpty)
            const Text('No contact details are saved.')
          else
            for (final contact in contacts)
              KoloListRow(
                  title: contact.value,
                  subtitle:
                      '${labelFor(contactKinds, contact.kind)} · ${contact.isPublic ? 'public' : 'private'}',
                  icon: Icons.contact_phone_outlined),
        ],
      );
}

class _ContactDraft {
  _ContactDraft(this.kind, String value, this.isPublic)
      : value = TextEditingController(text: value);
  String kind;
  final TextEditingController value;
  bool isPublic;
}

class _ContactsForm extends StatefulWidget {
  const _ContactsForm(
      {required this.repository,
      required this.businessId,
      required this.initial});
  final LiveBusinessRepository repository;
  final String businessId;
  final List<ProfileContact> initial;
  @override
  State<_ContactsForm> createState() => _ContactsFormState();
}

class _ContactsFormState extends State<_ContactsForm> {
  late final List<_ContactDraft> _rows = [
    for (final c in widget.initial) _ContactDraft(c.kind, c.value, c.isPublic)
  ];
  final _attempt = AttemptKey();
  bool _busy = false, _saved = false;
  Object? _error;
  String? _problemText;

  @override
  void dispose() {
    for (final row in _rows) {
      row.value.dispose();
    }
    super.dispose();
  }

  List<ProfileContact> get _contacts => [
        for (final row in _rows)
          ProfileContact(row.kind, row.value.text.trim(), row.isPublic)
      ];

  String? _check() {
    for (final c in _contacts) {
      if (c.value.isEmpty) return 'Fill in or remove every contact row.';
      if (c.kind == 'website' && !c.value.startsWith('https://')) {
        return 'Website addresses must start with https://';
      }
    }
    return null;
  }

  Future<void> _save() async {
    if (_busy) return;
    final problem = _check();
    if (problem != null) {
      setState(() => _problemText = problem);
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _problemText = null;
    });
    try {
      await widget.repository.editProfile(widget.businessId,
          contacts: _contacts,
          key: _attempt.forContent([
            for (final c in _contacts) '${c.kind}:${c.value}:${c.isPublic}'
          ].join('|')));
      _attempt.reset();
      if (mounted) setState(() => _saved = true);
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => UnsavedChangesGuard(
        dirty: !_saved,
        busy: _busy,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const KoloNote(
                title: 'Who can see these',
                message:
                    'A contact marked public is shown to signed-in people with a verified email address. Others stay private to your team and KoloVibe reviewers.',
                icon: Icons.visibility_outlined),
            const SizedBox(height: 12),
            for (var i = 0; i < _rows.length; i++) _row(i),
            if (_rows.length < 10)
              Align(
                alignment: Alignment.centerLeft,
                child: KoloPillButton(
                    label: 'Add a contact',
                    onPressed: _busy
                        ? null
                        : () => setState(
                            () => _rows.add(_ContactDraft('phone', '', true)))),
              ),
            const SizedBox(height: 12),
            if (_problemText != null) _problem(_problemText!),
            if (_error != null)
              SendError(error: _error!, returnTo: BusinessScreens.myBusinesses),
            if (_saved)
              const Padding(
                padding: EdgeInsets.only(bottom: 12),
                child: KoloNote(
                    key: ValueKey('contacts-saved'),
                    title: 'Saved as a draft',
                    message:
                        'Submit it from Profile review to have it checked.',
                    tone: KoloNoteTone.success,
                    icon: Icons.check_circle_outline),
              ),
            FilledButton(
                onPressed: _busy ? null : _save,
                child: Text(_busy ? 'Saving…' : 'Save draft')),
          ],
        ),
      );

  Widget _row(int index) {
    final row = _rows[index];
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: DecoratedBox(
        decoration: BoxDecoration(
            border: Border.all(color: KoloVibeColors.line),
            borderRadius: BorderRadius.circular(KoloVibeRadii.tile)),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(children: [
            DropdownButtonFormField<String>(
              key: ValueKey('contact-kind-$index'),
              initialValue: row.kind,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Kind'),
              items: [
                for (final k in contactKinds)
                  DropdownMenuItem(value: k.code, child: Text(k.label))
              ],
              onChanged: _busy
                  ? null
                  : (v) => setState(() => row.kind = v ?? row.kind),
            ),
            const SizedBox(height: 12),
            KoloTextField(
                label: 'Value',
                controller: row.value,
                maxLength: 300,
                readOnly: _busy),
            SwitchListTile(
              key: ValueKey('contact-public-$index'),
              contentPadding: EdgeInsets.zero,
              title: const Text('Public'),
              value: row.isPublic,
              onChanged: _busy ? null : (v) => setState(() => row.isPublic = v),
            ),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(
                  key: ValueKey('contact-remove-$index'),
                  onPressed: _busy
                      ? null
                      : () =>
                          setState(() => _rows.removeAt(index).value.dispose()),
                  child: const Text('Remove')),
            ),
          ]),
        ),
      ),
    );
  }
}

// ---- M-131 Opening hours ------------------------------------------------------------------------------------------

/// Times in 15-minute steps, from 00:00 to 24:00 (24:00 means the end of the day).
final List<String> hoursChoices = [
  for (var m = 0; m <= 24 * 60; m += 15)
    '${(m ~/ 60).toString().padLeft(2, '0')}:${(m % 60).toString().padLeft(2, '0')}'
];

class BusinessEditHoursScreen extends StatelessWidget {
  const BusinessEditHoursScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.businessId});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final String businessId;

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.editHours,
        catalog: catalog,
        title: 'Opening hours',
        showNavigation: false,
        child: BusinessLoader<BusinessProfile>(
          onSignIn: () => _signIn(context, BusinessScreens.myBusinesses),
          load: () => repository.profile(businessId),
          builder: (context, profile, reload) => _HoursForm(
              repository: repository,
              businessId: businessId,
              initial: profile.hours,
              timeZone: (profile.working ?? profile.approved)?.timeZone),
        ),
      );
}

class _Range {
  _Range(this.opens, this.closes);
  String opens, closes;
}

class _HoursForm extends StatefulWidget {
  const _HoursForm(
      {required this.repository,
      required this.businessId,
      required this.initial,
      required this.timeZone});
  final LiveBusinessRepository repository;
  final String businessId;
  final BusinessHours initial;
  final String? timeZone;
  @override
  State<_HoursForm> createState() => _HoursFormState();
}

class _ExceptionDraft {
  _ExceptionDraft(String date, this.closed, this.opens, this.closes)
      : date = TextEditingController(text: date);
  final TextEditingController date;
  bool closed;
  String opens, closes;
}

class _HoursFormState extends State<_HoursForm> {
  late final List<List<_Range>> _days = [
    for (var day = 0; day < 7; day++)
      [
        for (final r in widget.initial.rules.where((r) => r.weekday == day))
          _Range(r.opens, r.closes)
      ]
  ];
  late final List<_ExceptionDraft> _exceptions = [
    for (final e in widget.initial.exceptions)
      _ExceptionDraft(
          e.onDate, e.closed, e.opens ?? '09:00', e.closes ?? '17:00')
  ];
  final _attempt = AttemptKey();
  bool _busy = false, _saved = false;
  Object? _error;
  String? _problemText;

  @override
  void dispose() {
    for (final e in _exceptions) {
      e.date.dispose();
    }
    super.dispose();
  }

  static bool _validDate(String text) {
    if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(text)) return false;
    final parsed = DateTime.tryParse(text);
    return parsed != null &&
        '${parsed.year.toString().padLeft(4, '0')}-${parsed.month.toString().padLeft(2, '0')}-${parsed.day.toString().padLeft(2, '0')}' ==
            text;
  }

  ({List<HoursRule> rules, List<HoursException> exceptions})? _build() {
    final rules = <HoursRule>[];
    for (var day = 0; day < 7; day++) {
      for (final r in _days[day]) {
        if (r.opens.compareTo(r.closes) >= 0) {
          setState(() => _problemText =
              '${weekdays[day]}: closing time must be after opening time.');
          return null;
        }
        rules.add(HoursRule(day, r.opens, r.closes));
      }
    }
    final exceptions = <HoursException>[];
    for (final e in _exceptions) {
      final date = e.date.text.trim();
      if (!_validDate(date)) {
        setState(() => _problemText =
            'Enter special days as YYYY-MM-DD, for example 2026-12-25.');
        return null;
      }
      if (!e.closed && e.opens.compareTo(e.closes) >= 0) {
        setState(() =>
            _problemText = '$date: closing time must be after opening time.');
        return null;
      }
      exceptions.add(HoursException(date, e.closed, e.closed ? null : e.opens,
          e.closed ? null : e.closes));
    }
    if (rules.length > 28 || exceptions.length > 60) {
      setState(
          () => _problemText = 'That is more opening times than can be saved.');
      return null;
    }
    return (rules: rules, exceptions: exceptions);
  }

  Future<void> _save() async {
    if (_busy) return;
    setState(() => _problemText = null);
    final built = _build();
    if (built == null) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.repository.replaceHours(
          widget.businessId, built.rules, built.exceptions,
          key: _attempt.forContent([
            for (final r in built.rules) '${r.weekday}${r.opens}${r.closes}',
            for (final e in built.exceptions)
              '${e.onDate}${e.closed}${e.opens}${e.closes}'
          ].join('|')));
      _attempt.reset();
      if (!mounted) return;
      setState(() => _saved = true);
      notifySuccess(context, 'Opening hours saved');
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => UnsavedChangesGuard(
        dirty: !_saved,
        busy: _busy,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
                widget.timeZone == null
                    ? 'Times are in the business time zone.'
                    : 'Times are in ${widget.timeZone}.',
                style: KoloVibeText.body(12)),
            const SizedBox(height: 4),
            const Text(
                'Opening hours take effect as soon as they are saved. A day with no times is shown as closed. If you save no times at all, customers are told the hours are not published.'),
            const SizedBox(height: 12),
            for (var day = 0; day < 7; day++) _day(day),
            const SizedBox(height: 8),
            const KoloSectionHeading(title: 'Special days'),
            const SizedBox(height: 8),
            for (var i = 0; i < _exceptions.length; i++) _exception(i),
            Align(
              alignment: Alignment.centerLeft,
              child: KoloPillButton(
                  label: 'Add a special day',
                  onPressed: _busy
                      ? null
                      : () => setState(() => _exceptions
                          .add(_ExceptionDraft('', true, '09:00', '17:00')))),
            ),
            const SizedBox(height: 12),
            if (_problemText != null) _problem(_problemText!),
            if (_error != null)
              SendError(error: _error!, returnTo: BusinessScreens.myBusinesses),
            FilledButton(
                onPressed: _busy ? null : _save,
                child: Text(_busy ? 'Saving…' : 'Save opening hours')),
          ],
        ),
      );

  Widget _time(String key, String value, ValueChanged<String> onChanged) =>
      DropdownButton<String>(
        key: ValueKey(key),
        value: value,
        items: [
          for (final t in hoursChoices)
            DropdownMenuItem(value: t, child: Text(t))
        ],
        onChanged: _busy ? null : (v) => setState(() => onChanged(v ?? value)),
      );

  Widget _day(int day) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(weekdays[day],
              style: KoloVibeText.body(15, weight: FontWeight.w700)),
          if (_days[day].isEmpty) const Text('Closed'),
          for (var i = 0; i < _days[day].length; i++)
            Wrap(
                crossAxisAlignment: WrapCrossAlignment.center,
                spacing: 8,
                children: [
                  _time('open-$day-$i', _days[day][i].opens,
                      (v) => _days[day][i].opens = v),
                  const Text('to'),
                  _time('close-$day-$i', _days[day][i].closes,
                      (v) => _days[day][i].closes = v),
                  TextButton(
                      key: ValueKey('remove-$day-$i'),
                      onPressed: _busy
                          ? null
                          : () => setState(() => _days[day].removeAt(i)),
                      child: const Text('Remove')),
                ]),
          TextButton(
              key: ValueKey('add-$day'),
              onPressed: _busy
                  ? null
                  : () =>
                      setState(() => _days[day].add(_Range('08:00', '17:00'))),
              child: Text('Add times for ${weekdays[day]}')),
        ]),
      );

  Widget _exception(int i) {
    final e = _exceptions[i];
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: DecoratedBox(
        decoration: BoxDecoration(
            border: Border.all(color: KoloVibeColors.line),
            borderRadius: BorderRadius.circular(KoloVibeRadii.tile)),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            KoloTextField(
                label: 'Date (YYYY-MM-DD)',
                controller: e.date,
                maxLength: 10,
                readOnly: _busy),
            SwitchListTile(
              key: ValueKey('exception-closed-$i'),
              contentPadding: EdgeInsets.zero,
              title: const Text('Closed all day'),
              value: e.closed,
              onChanged: _busy ? null : (v) => setState(() => e.closed = v),
            ),
            if (!e.closed)
              Wrap(
                  crossAxisAlignment: WrapCrossAlignment.center,
                  spacing: 8,
                  children: [
                    _time('exception-open-$i', e.opens, (v) => e.opens = v),
                    const Text('to'),
                    _time('exception-close-$i', e.closes, (v) => e.closes = v),
                  ]),
            TextButton(
                key: ValueKey('exception-remove-$i'),
                onPressed: _busy
                    ? null
                    : () =>
                        setState(() => _exceptions.removeAt(i).date.dispose()),
                child: const Text('Remove')),
          ]),
        ),
      ),
    );
  }
}

// ---- M-132 Profile review status ----------------------------------------------------------------------------------

class BusinessProfileStatusScreen extends StatelessWidget {
  const BusinessProfileStatusScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.businessId});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final String businessId;

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.profileStatus,
        catalog: catalog,
        title: 'Profile review',
        showNavigation: false,
        child: BusinessLoader<BusinessProfile>(
          onSignIn: () => _signIn(context, BusinessScreens.myBusinesses),
          load: () => repository.profile(businessId),
          builder: (context, profile, reload) => _ProfileStatus(
              repository: repository,
              businessId: businessId,
              profile: profile,
              reload: reload),
        ),
      );
}

class _ProfileStatus extends StatefulWidget {
  const _ProfileStatus(
      {required this.repository,
      required this.businessId,
      required this.profile,
      required this.reload});
  final LiveBusinessRepository repository;
  final String businessId;
  final BusinessProfile profile;
  final VoidCallback reload;
  @override
  State<_ProfileStatus> createState() => _ProfileStatusState();
}

class _ProfileStatusState extends State<_ProfileStatus> {
  final _attempt = AttemptKey();
  bool _busy = false;
  Object? _error;

  Future<void> _submit() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final revision = await widget.repository
          .submitProfile(widget.businessId, key: _attempt.forContent('submit'));
      _attempt.reset();
      if (!mounted) return;
      notifySuccess(
          context,
          revision.applied == true
              ? 'Your change went live straight away.'
              : 'Submitted. KoloVibe reviewers will check it before it goes live.');
      widget.reload();
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _revision(String heading, ProfileRevision revision,
          {String? reason}) =>
      Padding(
        padding: const EdgeInsets.only(bottom: 16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          KoloSectionHeading(title: heading),
          const SizedBox(height: 4),
          Text(revision.name,
              style: KoloVibeText.body(15, weight: FontWeight.w700)),
          if (revision.description.isNotEmpty) Text(revision.description),
          Text([revision.city, countyLabel(revision.countyCode)]
              .where((p) => p.isNotEmpty)
              .join(', ')),
          if (reason != null) Text('Reviewer reason: ${reasonText(reason)}'),
        ]),
      );

  @override
  Widget build(BuildContext context) {
    final profile = widget.profile;
    final working = profile.working;
    final canSubmit = working != null && working.state == 'draft';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (profile.approved != null)
          _revision('Public profile', profile.approved!)
        else
          const KoloInlineState(
              title: 'No public profile yet',
              message:
                  'Nothing is shown to customers until a profile has been approved and the business is listed.',
              icon: Icons.visibility_off_outlined),
        if (working != null)
          _revision(
              working.state == 'pending_review'
                  ? 'Waiting for review'
                  : 'Draft change',
              working),
        if (profile.lastRejected != null)
          _revision('Last change not approved', profile.lastRejected!,
              reason: profile.lastRejected!.reasonCode),
        if (_error != null)
          SendError(
              error: _error!,
              returnTo: BusinessScreens.myBusinesses,
              title: 'Not submitted'),
        if (working != null && working.state == 'pending_review')
          const Text(
              'This change is waiting for a reviewer. You cannot change the profile again until it is decided.'),
        if (canSubmit)
          FilledButton(
              onPressed: _busy ? null : _submit,
              child: Text(_busy ? 'Submitting…' : 'Submit for review')),
        if (working == null)
          OutlinedButton(
              onPressed: () => _go(context, BusinessScreens.editProfile,
                  entityId: widget.businessId),
              child: const Text('Edit business details')),
      ],
    );
  }
}

// ---- M-133 Verification -------------------------------------------------------------------------------------------

class BusinessVerificationScreen extends StatelessWidget {
  const BusinessVerificationScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.businessId});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final String businessId;

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.verification,
        catalog: catalog,
        title: 'Verification',
        showNavigation: false,
        child: BusinessLoader<VerificationStatus>(
          onSignIn: () => _signIn(context, BusinessScreens.myBusinesses),
          load: () => repository.verificationStatus(businessId),
          builder: (context, status, reload) => _Verification(
              repository: repository,
              businessId: businessId,
              status: status,
              reload: reload),
        ),
      );
}

class _EvidenceRow {
  _EvidenceRow(this.kind) : value = TextEditingController();
  String kind;
  final TextEditingController value;
}

class _Verification extends StatefulWidget {
  const _Verification(
      {required this.repository,
      required this.businessId,
      required this.status,
      required this.reload});
  final LiveBusinessRepository repository;
  final String businessId;
  final VerificationStatus status;
  final VoidCallback reload;
  @override
  State<_Verification> createState() => _VerificationState();
}

class _VerificationState extends State<_Verification> {
  final List<_EvidenceRow> _rows = [_EvidenceRow(evidenceKinds.first.code)];
  final _attempt = AttemptKey();
  bool _declared = false, _busy = false;
  Object? _error;
  String? _problemText;

  @override
  void dispose() {
    for (final row in _rows) {
      row.value.dispose();
    }
    super.dispose();
  }

  bool get _answering => widget.status.state == 'needs_info';
  bool get _canSubmit => const {'none', 'rejected', 'revoked', 'needs_info'}
      .contains(widget.status.state);

  Future<void> _send() async {
    if (_busy) return;
    final evidence = [
      for (final r in _rows) (kind: r.kind, value: r.value.text.trim())
    ];
    if (evidence.any((e) => e.value.length < 2)) {
      setState(() => _problemText = 'Fill in or remove every evidence row.');
      return;
    }
    if (!_answering && !_declared) {
      setState(() => _problemText = 'Confirm the declaration to continue.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _problemText = null;
    });
    final fingerprint =
        [for (final e in evidence) '${e.kind}:${e.value}'].join('|');
    try {
      if (_answering) {
        await widget.repository.respondToVerification(widget.businessId,
            evidence: evidence, key: _attempt.forContent(fingerprint));
      } else {
        await widget.repository.submitVerification(widget.businessId,
            method: verificationMethods.first.code,
            evidence: evidence,
            key: _attempt.forContent(fingerprint));
      }
      _attempt.reset();
      if (!mounted) return;
      notifySuccess(context, 'Sent for review');
      widget.reload();
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String get _statusText => switch (widget.status.state) {
        'none' => 'Not submitted yet',
        'submitted' => 'Submitted. Waiting for a reviewer.',
        'under_review' => 'A reviewer is looking at it.',
        'needs_info' => 'The reviewer needs more information.',
        'verified' => 'Verified',
        'rejected' => 'Not approved',
        'revoked' => 'Verification was withdrawn',
        final other => other,
      };

  @override
  Widget build(BuildContext context) {
    final status = widget.status;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        KoloNote(
            key: const ValueKey('verification-status'),
            title: _statusText,
            message: [
              if (status.submittedAt != null)
                'Submitted ${dateLabel(status.submittedAt!)}.',
              if (status.decidedAt != null)
                'Decided ${dateLabel(status.decidedAt!)}.',
              if (status.reasonCode != null)
                'Reviewer reason: ${reasonText(status.reasonCode!)}.',
            ].join(' '),
            icon: status.state == 'verified'
                ? Icons.verified_outlined
                : Icons.fact_check_outlined),
        const SizedBox(height: 16),
        if (_canSubmit) ...[
          KoloSectionHeading(
              title:
                  _answering ? 'Answer the request' : 'Send for verification'),
          const SizedBox(height: 8),
          const Text(
              'Give text details a reviewer can check, such as a registration number. Files and photos cannot be sent in this version.'),
          const SizedBox(height: 12),
          for (var i = 0; i < _rows.length; i++) _row(i),
          if (_rows.length < 5)
            Align(
              alignment: Alignment.centerLeft,
              child: KoloPillButton(
                  label: 'Add another detail',
                  onPressed: _busy
                      ? null
                      : () => setState(() =>
                          _rows.add(_EvidenceRow(evidenceKinds.first.code)))),
            ),
          if (!_answering)
            CheckboxListTile(
              key: const ValueKey('verification-declaration'),
              contentPadding: EdgeInsets.zero,
              controlAffinity: ListTileControlAffinity.leading,
              title: const Text(
                  'I confirm this information is true and I am allowed to act for this business.'),
              value: _declared,
              onChanged:
                  _busy ? null : (v) => setState(() => _declared = v ?? false),
            ),
          if (_problemText != null) _problem(_problemText!),
          if (_error != null)
            SendError(
                error: _error!,
                returnTo: BusinessScreens.myBusinesses,
                title: 'Not sent'),
          FilledButton(
              onPressed: _busy ? null : _send,
              child: Text(_busy
                  ? 'Sending…'
                  : (_answering ? 'Send answer' : 'Send for verification'))),
        ],
      ],
    );
  }

  Widget _row(int i) {
    final row = _rows[i];
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(children: [
        DropdownButtonFormField<String>(
          key: ValueKey('evidence-kind-$i'),
          initialValue: row.kind,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'What is it?'),
          items: [
            for (final k in evidenceKinds)
              DropdownMenuItem(value: k.code, child: Text(k.label))
          ],
          onChanged:
              _busy ? null : (v) => setState(() => row.kind = v ?? row.kind),
        ),
        const SizedBox(height: 8),
        KoloTextField(
            label: 'Details',
            controller: row.value,
            maxLength: 300,
            readOnly: _busy),
        if (_rows.length > 1)
          Align(
            alignment: Alignment.centerRight,
            child: TextButton(
                key: ValueKey('evidence-remove-$i'),
                onPressed: _busy
                    ? null
                    : () => setState(() => _rows.removeAt(i).value.dispose()),
                child: const Text('Remove')),
          ),
      ]),
    );
  }
}

// ---- M-134 Listing ------------------------------------------------------------------------------------------------

class BusinessListingScreen extends StatelessWidget {
  const BusinessListingScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.businessId});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final String businessId;

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.listing,
        catalog: catalog,
        title: 'Listing',
        showNavigation: false,
        child: BusinessLoader<ListingStatus>(
          onSignIn: () => _signIn(context, BusinessScreens.myBusinesses),
          load: () => repository.listingStatus(businessId),
          builder: (context, status, reload) => _Listing(
              repository: repository, businessId: businessId, initial: status),
        ),
      );
}

class _Listing extends StatefulWidget {
  const _Listing(
      {required this.repository,
      required this.businessId,
      required this.initial});
  final LiveBusinessRepository repository;
  final String businessId;
  final ListingStatus initial;
  @override
  State<_Listing> createState() => _ListingState();
}

class _ListingState extends State<_Listing> {
  late ListingStatus _status = widget.initial;
  final _attempt = AttemptKey();
  bool _busy = false;
  Object? _error;

  Future<void> _change(bool publish) async {
    if (_busy) return;
    if (!publish) {
      final ok = await confirmDestructive(context,
          title: 'Hide this business?',
          message:
              'It will stop appearing in search and customers will no longer find it.',
          confirmLabel: 'Hide business');
      if (!ok || !mounted) return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final key = _attempt.forContent(publish ? 'publish' : 'unpublish');
      final next = publish
          ? await widget.repository.publish(widget.businessId, key: key)
          : await widget.repository.unpublish(widget.businessId, key: key);
      _attempt.reset();
      if (mounted) setState(() => _status = next);
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final status = _status;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        KoloNote(
            key: const ValueKey('listing-state'),
            title: status.listed ? 'Listed publicly' : 'Not listed',
            message: status.listed
                ? 'Customers can find this business in search.'
                : 'Customers cannot find this business in search.',
            icon: status.listed ? Icons.public : Icons.visibility_off_outlined),
        const SizedBox(height: 12),
        if (!status.eligible) ...[
          const Text('Before it can be listed:'),
          for (final reason in status.reasons)
            Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text('• ${listingReasonLabel(reason)}')),
          const SizedBox(height: 12),
        ],
        if (_error != null)
          SendError(error: _error!, returnTo: BusinessScreens.myBusinesses),
        if (status.eligible && !status.ownerWantsListing)
          FilledButton(
              onPressed: _busy ? null : () => _change(true),
              child: Text(_busy ? 'Please wait…' : 'Show in search')),
        if (status.ownerWantsListing)
          OutlinedButton(
              onPressed: _busy ? null : () => _change(false),
              child: Text(_busy ? 'Please wait…' : 'Hide from search')),
      ],
    );
  }
}

/// Copies [code] to the clipboard and says so.
Future<void> copyCode(BuildContext context, String code) async {
  await Clipboard.setData(ClipboardData(text: code));
  if (context.mounted) {
    ScaffoldMessenger.of(context)
        .showSnackBar(const SnackBar(content: Text('Code copied')));
  }
}
