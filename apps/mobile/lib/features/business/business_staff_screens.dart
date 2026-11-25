import 'package:flutter/material.dart';

import '../../core/presentation/design_node.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/kolo_components.dart';
import '../system/system_ui.dart';
import 'business_access.dart';
import 'business_context.dart';
import 'business_models.dart';
import 'business_owner_screens.dart' show SendError;
import 'business_page.dart';
import 'business_screens.dart';
import 'business_ui.dart';
import 'live_business_repository.dart';

// ---- M-140 Accept an invitation -----------------------------------------------------------------------------------

class BusinessRedeemScreen extends StatefulWidget {
  const BusinessRedeemScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.context});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final BusinessContext? context;
  @override
  State<BusinessRedeemScreen> createState() => _BusinessRedeemScreenState();
}

class _BusinessRedeemScreenState extends State<BusinessRedeemScreen> {
  final _code = TextEditingController();
  final _attempt = AttemptKey();
  bool _busy = false, _done = false;
  Object? _error;
  String? _problemText;

  @override
  void dispose() {
    // The invitation code is a secret: it is wiped with the screen and never stored.
    _code.clear();
    _code.dispose();
    super.dispose();
  }

  Future<void> _redeem() async {
    if (_busy) return;
    final code = _code.text.trim();
    if (code.length < 16) {
      setState(() => _problemText = 'Enter the whole code you were given.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _problemText = null;
    });
    try {
      final business =
          await widget.repository.redeem(code, key: _attempt.forContent(code));
      _attempt.reset();
      final account = widget.repository.account.signedInAccountId;
      if (account != null) await widget.context?.select(account, business.id);
      if (!mounted) return;
      _done = true;
      _code.clear();
      notifySuccess(context, 'You joined ${business.name}');
      replaceBusiness(context, BusinessScreens.staffHome, entityId: business.id);
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  /// The service answers an unknown, used, revoked and expired code the same way, so the app does too.
  String _message(Object error) => isNotFoundFailure(error)
      ? 'This code did not work. Check it, or ask the business owner for a new one.'
      : failureText(error);

  @override
  Widget build(BuildContext context) => UnsavedChangesGuard(
        dirty: !_done && _code.text.trim().isNotEmpty,
        busy: _busy,
        child: BusinessPage(
          screen: BusinessScreens.redeem,
          catalog: widget.catalog,
          title: 'Join a business team',
          showNavigation: false,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const KoloNote(
                  title: 'Use the code the owner gave you',
                  message:
                      'A business owner can invite you to work with them. You get a one-time code from them; enter it here. Staff can answer customers and edit opening hours.',
                  icon: Icons.group_add_outlined),
              const SizedBox(height: 16),
              KoloTextField(
                  label: 'Invitation code',
                  controller: _code,
                  secret: true,
                  maxLength: 64,
                  readOnly: _busy,
                  onChanged: (_) => setState(() {}),
                  onSubmitted: (_) => _redeem()),
              if (_problemText != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Text(_problemText!,
                      style: KoloVibeText.body(13, color: KoloVibeColors.red)),
                ),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: needsSignIn(_error!)
                      ? SendError(
                          error: _error!,
                          returnTo: BusinessScreens.redeem,
                          title: 'Not joined')
                      : KoloInlineState(
                          title: 'Not joined',
                          message: _message(_error!),
                          icon: Icons.error_outline),
                ),
              FilledButton(
                  onPressed: _busy ? null : _redeem,
                  child: Text(_busy ? 'Checking…' : 'Join business')),
            ],
          ),
        ),
      );
}

// ---- M-141 Switch business ----------------------------------------------------------------------------------------

class BusinessSwitcherScreen extends StatelessWidget {
  const BusinessSwitcherScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.context});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final BusinessContext? context;

  /// Every business the service says this person may work in, and the remembered choice if it is still one of them.
  Future<({List<MyBusiness> businesses, String? current, bool lost})>
      _load() async {
    final all = <MyBusiness>[];
    String? cursor;
    for (var page = 0; page < 5; page++) {
      final result = await repository.myBusinesses(cursor: cursor);
      all.addAll(result.items);
      cursor = result.nextCursor;
      if (cursor == null) break;
    }
    final account = repository.account.signedInAccountId;
    var current =
        account == null ? context?.businessId : await context?.restore(account);
    var lost = false;
    if (current != null && !all.any((b) => b.id == current)) {
      // Remembered, but the service no longer lists it: access was removed. Forget it.
      await context?.clear();
      current = null;
      lost = true;
    }
    return (businesses: all, current: current, lost: lost);
  }

  @override
  Widget build(BuildContext screen) => BusinessPage(
        screen: BusinessScreens.switcher,
        catalog: catalog,
        title: 'Switch business',
        child: BusinessLoader<
            ({List<MyBusiness> businesses, String? current, bool lost})>(
          onSignIn: () => signInForBusiness(screen, BusinessScreens.switcher),
          load: _load,
          builder: (screen, data, reload) => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (data.lost)
                const Padding(
                  padding: EdgeInsets.only(bottom: 12),
                  child: KoloNote(
                      key: ValueKey('access-lost'),
                      title: 'Access removed',
                      message:
                          'You no longer have access to the business you had selected. Choose another.',
                      icon: Icons.lock_outline,
                      tone: KoloNoteTone.alert),
                ),
              if (data.businesses.isEmpty)
                const KoloInlineState(
                  title: 'No businesses',
                  message:
                      'Register a business or join a team with an invitation code.',
                  icon: Icons.storefront_outlined,
                ),
              for (final business in data.businesses)
                KoloListRow(
                  title: business.name,
                  subtitle:
                      '${roleLabel(business.role)} · ${businessStateLabel(business.state)}',
                  icon: business.id == data.current
                      ? Icons.check_circle
                      : Icons.chevron_right,
                  onTap: () async {
                    final account = repository.account.signedInAccountId;
                    if (account != null) {
                      await context?.select(account, business.id);
                    }
                    if (!screen.mounted) return;
                    replaceBusiness(
                        screen,
                        business.isOwner
                            ? BusinessScreens.manage
                            : BusinessScreens.staffHome,
                        entityId: business.id);
                  },
                ),
              const SizedBox(height: 12),
              KoloListRow(
                  title: 'Join a business team',
                  onTap: () => openBusiness(screen, BusinessScreens.redeem)),
              KoloListRow(
                  title: 'Register a business',
                  divider: false,
                  onTap: () => openBusiness(screen, BusinessScreens.register)),
            ],
          ),
        ),
      );
}

// ---- M-142 Access removed -----------------------------------------------------------------------------------------

class BusinessAccessRemovedScreen extends StatelessWidget {
  const BusinessAccessRemovedScreen(
      {super.key, required this.catalog, required this.context});
  final DesignCatalog catalog;
  final BusinessContext? context;

  @override
  Widget build(BuildContext screen) => BusinessPage(
        screen: BusinessScreens.accessRemoved,
        catalog: catalog,
        title: 'Access removed',
        scroll: false,
        child: const AccessRemovedBody(),
      );
}

// ---- M-143 Leave a business ---------------------------------------------------------------------------------------

class BusinessLeaveScreen extends StatelessWidget {
  const BusinessLeaveScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.businessId,
      required this.context});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final String businessId;
  final BusinessContext? context;

  @override
  Widget build(BuildContext screen) => BusinessPage(
        screen: BusinessScreens.leave,
        catalog: catalog,
        title: 'Leave business',
        showNavigation: false,
        child: BusinessLoader<MyBusiness>(
          onSignIn: () => signInForBusiness(screen, BusinessScreens.myBusinesses),
          errorBuilder: (screen, error) =>
              accessLost(error) ? const AccessRemovedBody() : null,
          load: () => repository.business(businessId),
          builder: (screen, business, reload) => _Leave(
              repository: repository, business: business, context: context),
        ),
      );
}

class _Leave extends StatefulWidget {
  const _Leave(
      {required this.repository,
      required this.business,
      required this.context});
  final LiveBusinessRepository repository;
  final MyBusiness business;
  final BusinessContext? context;
  @override
  State<_Leave> createState() => _LeaveState();
}

class _LeaveState extends State<_Leave> {
  final _attempt = AttemptKey();
  bool _busy = false;
  Object? _error;

  Future<void> _leave() async {
    if (_busy) return;
    final ok = await confirmDestructive(context,
        title: 'Leave ${widget.business.name}?',
        message:
            'You will lose access to its inbox and opening hours. The owner can invite you again.',
        confirmLabel: 'Leave business');
    if (!ok || !mounted) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.repository
          .leave(widget.business.id, key: _attempt.forContent('leave'));
      _attempt.reset();
      if (widget.context?.businessId == widget.business.id) {
        await widget.context?.clear();
      }
      if (!mounted) return;
      notifySuccess(context, 'You left ${widget.business.name}');
      replaceBusiness(context, BusinessScreens.myBusinesses);
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final owner = widget.business.isOwner;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(widget.business.name, style: KoloVibeText.heading(20)),
        const SizedBox(height: 12),
        if (owner)
          const KoloNote(
              key: ValueKey('owner-cannot-leave'),
              title: 'An owner cannot leave',
              message:
                  'The owner of a business cannot leave it. Only staff can leave a business.',
              icon: Icons.info_outline)
        else ...[
          const Text(
              'Leaving removes your access to this business’s inbox and opening hours. Conversations you had stay with the business.'),
          const SizedBox(height: 12),
          if (_error != null)
            SendError(
                error: _error!,
                returnTo: BusinessScreens.myBusinesses,
                title: 'Not done'),
          FilledButton(
              key: const ValueKey('leave-business'),
              onPressed: _busy ? null : _leave,
              child: Text(_busy ? 'Please wait…' : 'Leave business')),
        ],
      ],
    );
  }
}
