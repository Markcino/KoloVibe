import 'package:flutter/material.dart';

import '../../core/presentation/design_node.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/kolo_components.dart';
import '../system/system_ui.dart';
import 'business_lists.dart';
import 'business_models.dart';
import 'business_owner_screens.dart' show SendError, copyCode;
import 'business_page.dart';
import 'business_screens.dart';
import 'business_ui.dart';
import 'live_business_repository.dart';

void _go(BuildContext context, int screen, {String? entityId}) =>
    openBusiness(context, screen, entityId: entityId);

void _signIn(BuildContext context, int returnTo) =>
    openBusiness(context, 4, returnTo: returnTo);

// ---- M-135 Inbox --------------------------------------------------------------------------------------------------

class BusinessInboxScreen extends StatelessWidget {
  const BusinessInboxScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.businessId});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final String businessId;

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.inbox,
        catalog: catalog,
        title: 'Inbox',
        scroll: false,
        child: BusinessPagedList<BusinessInquiry>(
          onSignIn: () => _signIn(context, BusinessScreens.myBusinesses),
          fetch: (cursor) => repository.inbox(businessId, cursor: cursor),
          empty: const KoloInlineState(
            title: 'No questions yet',
            message: 'Questions from customers appear here.',
            icon: Icons.inbox_outlined,
          ),
          itemBuilder: (context, inquiry) => KoloListRow(
            title: inquiry.customerLabel,
            subtitle: [
              if (inquiry.subjectCode != null)
                labelFor(inquirySubjects, inquiry.subjectCode!),
              inquiry.state == InquiryState.open ? 'Open' : 'Closed',
              dateLabel(inquiry.createdAt),
            ].join(' · '),
            onTap: () => _go(context, BusinessScreens.inboxThread,
                entityId: ReviewTarget(businessId, inquiry.id).encoded),
          ),
        ),
      );
}

// ---- M-136 Inbox conversation -------------------------------------------------------------------------------------

class BusinessInboxThreadScreen extends StatelessWidget {
  const BusinessInboxThreadScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.target});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final ReviewTarget target;

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.inboxThread,
        catalog: catalog,
        title: 'Conversation',
        showNavigation: false,
        child: BusinessLoader<(BusinessInquiry, MyBusiness)>(
          onSignIn: () => _signIn(context, BusinessScreens.myBusinesses),
          load: () async => (
            await repository.inboxThread(target.businessId, target.threadId!),
            await repository.business(target.businessId)
          ),
          builder: (context, data, reload) => _Thread(
              repository: repository,
              businessId: target.businessId,
              initial: data.$1,
              isOwner: data.$2.isOwner),
        ),
      );
}

class _Thread extends StatefulWidget {
  const _Thread(
      {required this.repository,
      required this.businessId,
      required this.initial,
      required this.isOwner});
  final LiveBusinessRepository repository;
  final String businessId;
  final BusinessInquiry initial;
  final bool isOwner;
  @override
  State<_Thread> createState() => _ThreadState();
}

class _ThreadState extends State<_Thread> {
  late BusinessInquiry _inquiry = widget.initial;
  final _reply = TextEditingController();
  final _sendKey = AttemptKey(),
      _closeKey = AttemptKey(),
      _confirmKey = AttemptKey(),
      _blockKey = AttemptKey();
  bool _busy = false;
  Object? _error;

  @override
  void dispose() {
    _reply.dispose();
    super.dispose();
  }

  Future<void> _run(Future<BusinessInquiry> Function() action,
      {VoidCallback? onDone}) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final answer = await action();
      if (!mounted) return;
      // Close, confirm and block answer without the messages; keep the ones already shown.
      setState(() => _inquiry = answer.messages.isEmpty
          ? BusinessInquiry(
              answer.id,
              answer.customerLabel,
              answer.state,
              answer.subjectCode,
              answer.createdAt,
              answer.confirmed,
              _inquiry.messages)
          : answer);
      onDone?.call();
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _send() async {
    final text = _reply.text.trim();
    if (text.isEmpty) return;
    await _run(
        () => widget.repository.reply(widget.businessId, _inquiry.id, text,
            key: _sendKey.forContent(text)), onDone: () {
      _sendKey.reset();
      _reply.clear();
    });
  }

  Future<void> _close() async {
    final ok = await confirmDestructive(context,
        title: 'Close this conversation?',
        message: 'Nobody can send more messages once it is closed.',
        confirmLabel: 'Close conversation');
    if (!ok || !mounted) return;
    await _run(() => widget.repository.closeThread(
        widget.businessId, _inquiry.id,
        key: _closeKey.forContent('close')));
  }

  Future<void> _block() async {
    final ok = await confirmDestructive(context,
        title: 'Stop this customer writing?',
        message:
            'This ends the conversation and the customer cannot write to the business again. The customer is not told that they were blocked.',
        confirmLabel: 'Block customer');
    if (!ok || !mounted) return;
    await _run(() => widget.repository.blockCustomer(
        widget.businessId, _inquiry.id,
        key: _blockKey.forContent('block')));
  }

  @override
  Widget build(BuildContext context) {
    final inquiry = _inquiry;
    final open = inquiry.state == InquiryState.open;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(inquiry.customerLabel,
            style: KoloVibeText.heading(20, height: 1.2)),
        const SizedBox(height: 4),
        Text(
            [
              if (inquiry.subjectCode != null)
                labelFor(inquirySubjects, inquiry.subjectCode!),
              open ? 'Open' : 'Closed',
            ].join(' · '),
            style: KoloVibeText.body(13)),
        const SizedBox(height: 16),
        for (final message in inquiry.messages) _bubble(context, message),
        if (!open)
          const Padding(
            padding: EdgeInsets.only(bottom: 12),
            child: KoloNote(
                title: 'This conversation is closed',
                message: 'No more messages can be sent.',
                icon: Icons.lock_outline),
          ),
        if (_error != null)
          SendError(
              error: _error!,
              returnTo: BusinessScreens.myBusinesses,
              title: 'Not sent'),
        if (open) ...[
          KoloTextField(
              label: 'Your reply',
              controller: _reply,
              maxLength: 1000,
              maxLines: 3,
              readOnly: _busy),
          FilledButton(
              onPressed: _busy ? null : _send,
              child: Text(_busy ? 'Please wait…' : 'Send reply')),
          const SizedBox(height: 16),
        ],
        Text(
            'Customer confirmed: ${inquiry.confirmed.customer ? 'yes' : 'not yet'} · You confirmed: ${inquiry.confirmed.business ? 'yes' : 'not yet'}',
            style: KoloVibeText.body(13)),
        const SizedBox(height: 4),
        const Text(
            'When both of you confirm that you dealt with each other, the customer can write a review based on it.'),
        if (open && !inquiry.confirmed.business)
          OutlinedButton(
              onPressed: _busy
                  ? null
                  : () => _run(() => widget.repository.confirmThread(
                      widget.businessId, _inquiry.id,
                      key: _confirmKey.forContent('confirm'))),
              child: const Text('We dealt with each other')),
        if (open)
          TextButton(
              onPressed: _busy ? null : _close,
              child: const Text('Close conversation')),
        if (widget.isOwner && open)
          TextButton(
              onPressed: _busy ? null : _block,
              child: const Text('Block this customer')),
      ],
    );
  }

  Widget _bubble(BuildContext context, InquiryMessage message) {
    final mine = message.fromBusiness;
    return Align(
      alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(12),
        constraints: const BoxConstraints(maxWidth: 300),
        decoration: BoxDecoration(
            color: mine ? KoloVibeColors.softBlue : Colors.white,
            border: Border.all(color: KoloVibeColors.line),
            borderRadius: BorderRadius.circular(KoloVibeRadii.tile)),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(mine ? 'Business' : _inquiry.customerLabel,
                style: KoloVibeText.body(11, weight: FontWeight.w700)),
            const SizedBox(height: 2),
            Text(message.removed ? 'This message was removed.' : message.body!,
                style: KoloVibeText.body(14, height: 1.4)),
            const SizedBox(height: 4),
            Text(dateLabel(message.createdAt), style: KoloVibeText.body(11)),
            if (!message.removed && !mine)
              TextButton(
                onPressed: () => _go(context, BusinessScreens.report,
                    entityId:
                        ReportTarget('inquiry_message', message.id).encoded),
                child: const Text('Report'),
              ),
          ],
        ),
      ),
    );
  }
}

// ---- M-137 Reviews and replies ------------------------------------------------------------------------------------

class BusinessOwnerReviewsScreen extends StatelessWidget {
  const BusinessOwnerReviewsScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.businessId});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final String businessId;

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.ownerReviews,
        catalog: catalog,
        title: 'Reviews and replies',
        scroll: false,
        child: BusinessPagedList<PublicReview>(
          onSignIn: () => _signIn(context, BusinessScreens.myBusinesses),
          fetch: (cursor) => repository.reviews(businessId, cursor: cursor),
          header: const Padding(
            padding: EdgeInsets.only(bottom: 12),
            child: KoloNote(
                title: 'You can answer, not change, reviews',
                message:
                    'A business cannot hide or edit a review. You can reply once to each published review, and remove your reply. Report a review that breaks the rules.',
                icon: Icons.rate_review_outlined),
          ),
          empty: const KoloInlineState(
              title: 'No reviews yet',
              message: 'Published reviews of your business appear here.',
              icon: Icons.rate_review_outlined),
          itemBuilder: (context, review) => _OwnerReviewTile(
              repository: repository, businessId: businessId, review: review),
        ),
      );
}

class _OwnerReviewTile extends StatefulWidget {
  const _OwnerReviewTile(
      {required this.repository,
      required this.businessId,
      required this.review});
  final LiveBusinessRepository repository;
  final String businessId;
  final PublicReview review;
  @override
  State<_OwnerReviewTile> createState() => _OwnerReviewTileState();
}

class _OwnerReviewTileState extends State<_OwnerReviewTile> {
  late OwnerResponse? _response = widget.review.response;
  final _text = TextEditingController();
  final _attempt = AttemptKey();
  bool _editing = false, _busy = false;
  Object? _error;
  String? _problemText;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_busy) return;
    final body = _text.text.trim();
    if (body.length < 2) {
      setState(() => _problemText = 'Write at least 2 characters.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _problemText = null;
    });
    try {
      final receipt = await widget.repository.respondToReview(
          widget.businessId, widget.review.id, body,
          key: _attempt.forContent(body));
      _attempt.reset();
      if (!mounted) return;
      setState(() {
        _response = OwnerResponse(receipt.body, receipt.createdAt);
        _editing = false;
      });
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _remove() async {
    if (_busy) return;
    final ok = await confirmDestructive(context,
        title: 'Remove your reply?',
        message: 'Customers will no longer see your reply to this review.',
        confirmLabel: 'Remove reply');
    if (!ok || !mounted) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.repository.deleteResponse(
          widget.businessId, widget.review.id,
          key: _attempt.forContent('delete'));
      _attempt.reset();
      if (mounted) setState(() => _response = null);
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final review = widget.review;
    return Padding(
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
              if (review.title != null)
                Text(review.title!,
                    style: KoloVibeText.body(15, weight: FontWeight.w700)),
              const SizedBox(height: 4),
              Text(review.body, style: KoloVibeText.body(14, height: 1.4)),
              const SizedBox(height: 8),
              Text(
                  '${review.authorLabel} · ${dateLabel(review.createdAt)} · ${reviewBasisLabel(review.basis)}',
                  style: KoloVibeText.body(12)),
              if (_response != null && !_editing) ...[
                const SizedBox(height: 8),
                KoloNote(
                    title: 'Your reply · ${dateLabel(_response!.createdAt)}',
                    message: _response!.body,
                    icon: Icons.reply),
              ],
              if (_editing) ...[
                const SizedBox(height: 8),
                KoloTextField(
                    label: 'Your reply',
                    controller: _text,
                    maxLength: 1000,
                    maxLines: 4,
                    readOnly: _busy),
                if (_problemText != null)
                  Text(_problemText!,
                      style: KoloVibeText.body(13, color: KoloVibeColors.red)),
              ],
              if (_error != null)
                SendError(
                    error: _error!,
                    returnTo: BusinessScreens.myBusinesses,
                    title: 'Not sent'),
              Wrap(children: [
                if (_editing) ...[
                  TextButton(
                      onPressed: _busy ? null : _save,
                      child: Text(_busy ? 'Saving…' : 'Save reply')),
                  TextButton(
                      onPressed:
                          _busy ? null : () => setState(() => _editing = false),
                      child: const Text('Cancel')),
                ] else ...[
                  TextButton(
                      onPressed: _busy
                          ? null
                          : () => setState(() {
                                _text.text = _response?.body ?? '';
                                _editing = true;
                              }),
                      child: Text(_response == null ? 'Reply' : 'Edit reply')),
                  if (_response != null)
                    TextButton(
                        onPressed: _busy ? null : _remove,
                        child: const Text('Remove reply')),
                  TextButton(
                      onPressed: () => _go(context, BusinessScreens.report,
                          entityId: ReportTarget('review', review.id).encoded),
                      child: const Text('Report review')),
                ],
              ]),
            ],
          ),
        ),
      ),
    );
  }
}

// ---- M-138 Review invitations -------------------------------------------------------------------------------------

class BusinessReviewInvitationsScreen extends StatefulWidget {
  const BusinessReviewInvitationsScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.businessId});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final String businessId;
  @override
  State<BusinessReviewInvitationsScreen> createState() =>
      _BusinessReviewInvitationsScreenState();
}

class _BusinessReviewInvitationsScreenState
    extends State<BusinessReviewInvitationsScreen> {
  // The code is held here only while this screen is open. Leaving the screen forgets it.
  OneTimeCode<ReviewInvitation>? _created;
  bool _busy = false;
  Object? _error;

  @override
  void dispose() {
    _created = null;
    super.dispose();
  }

  Future<void> _create() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      // A new key each time: a repeat of the same key would be answered without the code, which is shown only once.
      final made = await widget.repository.createReviewInvitation(
          widget.businessId,
          key: LiveBusinessRepository.newKey());
      if (mounted) setState(() => _created = made);
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _revoke() async {
    final made = _created;
    if (made == null || _busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.repository.revokeReviewInvitation(
          widget.businessId, made.value.id,
          key: LiveBusinessRepository.newKey());
      if (mounted) {
        setState(() => _created = null);
        notifySuccess(context, 'Invitation revoked');
      }
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.reviewInvitations,
        catalog: widget.catalog,
        title: 'Review invitations',
        showNavigation: false,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const KoloNote(
                title: 'Invite a customer to review you',
                message:
                    'Make a one-time code and give it to a customer. They enter it when they write a review, and the review is marked as invited by the business. You cannot choose what they write.',
                icon: Icons.rate_review_outlined),
            const SizedBox(height: 16),
            if (_error != null)
              SendError(
                  error: _error!,
                  returnTo: BusinessScreens.myBusinesses,
                  title: 'Not done'),
            if (_created != null)
              OneTimeCodeCard(
                title: 'Review invitation code',
                code: _created!.code,
                expiresAt: _created!.value.expiresAt,
                onCopy: () => copyCode(context, _created!.code),
                onDone: () => setState(() => _created = null),
                onRevoke: _busy ? null : _revoke,
              )
            else
              FilledButton(
                  onPressed: _busy ? null : _create,
                  child:
                      Text(_busy ? 'Please wait…' : 'Make an invitation code')),
          ],
        ),
      );
}

// ---- M-139 Team ---------------------------------------------------------------------------------------------------

class BusinessTeamScreen extends StatelessWidget {
  const BusinessTeamScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.businessId});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final String businessId;

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.team,
        catalog: catalog,
        title: 'Team',
        showNavigation: false,
        child: BusinessLoader<Team>(
          onSignIn: () => _signIn(context, BusinessScreens.myBusinesses),
          load: () => repository.team(businessId),
          builder: (context, team, reload) => _TeamBody(
              repository: repository, businessId: businessId, initial: team),
        ),
      );
}

class _TeamBody extends StatefulWidget {
  const _TeamBody(
      {required this.repository,
      required this.businessId,
      required this.initial});
  final LiveBusinessRepository repository;
  final String businessId;
  final Team initial;
  @override
  State<_TeamBody> createState() => _TeamBodyState();
}

class _TeamBodyState extends State<_TeamBody> {
  late Team _team = widget.initial;
  final _label = TextEditingController();
  OneTimeCode<StaffInvitation>? _created;
  bool _busy = false;
  Object? _error;
  String? _problemText;

  @override
  void dispose() {
    _created = null;
    _label.dispose();
    super.dispose();
  }

  Future<void> _refresh() async {
    try {
      final next = await widget.repository.team(widget.businessId);
      if (mounted) setState(() => _team = next);
    } catch (_) {
      // The list on screen stays as it was; the next action reloads it.
    }
  }

  Future<void> _invite() async {
    if (_busy) return;
    final label = _label.text.trim();
    if (label.isEmpty) {
      setState(() => _problemText =
          'Give the invitation a name, such as the person’s first name.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _problemText = null;
    });
    try {
      // A new key each time: a repeat of the same key would be answered without the code, which is shown only once.
      final made = await widget.repository.inviteStaff(widget.businessId, label,
          key: LiveBusinessRepository.newKey());
      if (!mounted) return;
      setState(() => _created = made);
      _label.clear();
      await _refresh();
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _revoke(StaffInvitation invitation) async {
    if (_busy) return;
    final ok = await confirmDestructive(context,
        title: 'Revoke this invitation?',
        message: 'The code stops working. You can make a new one.',
        confirmLabel: 'Revoke invitation');
    if (!ok || !mounted) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.repository.revokeInvitation(widget.businessId, invitation.id,
          key: LiveBusinessRepository.newKey());
      if (mounted && _created?.value.id == invitation.id) {
        setState(() => _created = null);
      }
      await _refresh();
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final pending =
        _team.invitations.where((i) => i.state == 'pending').toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const KoloSectionHeading(title: 'People'),
        for (final member in _team.members)
          KoloListRow(
            title: member.label.isEmpty ? roleLabel(member.role) : member.label,
            subtitle:
                '${roleLabel(member.role)}${member.isYou ? ' · you' : ''} · since ${dateLabel(member.since)}',
            icon: Icons.person_outline,
          ),
        const SizedBox(height: 8),
        const KoloNote(
            key: ValueKey('team-removal-unavailable'),
            title: 'Removing someone is not available yet',
            message:
                'Removing a team member needs an extra security check that is not available yet. You can revoke an unused invitation.',
            icon: Icons.lock_outline),
        const SizedBox(height: 16),
        const KoloSectionHeading(title: 'Invitations'),
        if (pending.isEmpty) const Text('No unused invitations.'),
        for (final invitation in pending)
          KoloListRow(
            title: invitation.label,
            subtitle: 'Expires ${dateLabel(invitation.expiresAt)}',
            icon: Icons.close,
            onTap: _busy ? null : () => _revoke(invitation),
          ),
        const SizedBox(height: 16),
        const KoloSectionHeading(title: 'Invite staff'),
        const SizedBox(height: 8),
        const Text(
            'Staff can answer customers and edit opening hours. They cannot change the profile, verification, listing, team or replies.'),
        const SizedBox(height: 8),
        if (_created != null)
          OneTimeCodeCard(
            title: 'Invitation code for ${_created!.value.label}',
            code: _created!.code,
            expiresAt: _created!.value.expiresAt,
            onCopy: () => copyCode(context, _created!.code),
            onDone: () => setState(() => _created = null),
            onRevoke: _busy ? null : () => _revoke(_created!.value),
          )
        else ...[
          KoloTextField(
              label: 'Name for this invitation',
              controller: _label,
              maxLength: 40,
              readOnly: _busy),
          if (_problemText != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(_problemText!,
                  style: KoloVibeText.body(13, color: KoloVibeColors.red)),
            ),
          if (_error != null)
            SendError(
                error: _error!,
                returnTo: BusinessScreens.myBusinesses,
                title: 'Not done'),
          FilledButton(
              onPressed: _busy ? null : _invite,
              child: Text(_busy ? 'Please wait…' : 'Make an invitation code')),
        ],
      ],
    );
  }
}
