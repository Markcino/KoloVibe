import 'package:flutter/material.dart';

import '../../app/screen_route.dart';
import '../../core/presentation/design_node.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/kolo_components.dart';
import '../system/system_ui.dart';
import 'business_lists.dart';
import 'business_models.dart';
import 'business_page.dart';
import 'business_screens.dart';
import 'business_ui.dart';
import 'live_business_repository.dart';

void _go(BuildContext context, int screen, {String? entityId}) =>
    openBusiness(context, screen, entityId: entityId);

/// Replaces the current screen, so back does not return to a finished form.
void _replace(BuildContext context, int screen, {String? entityId}) {
  final route = ScreenRoute(screen, entityId: entityId);
  Navigator.of(context).pushReplacementNamed(route.name, arguments: route);
}

/// A failed send, with a sign-in button when the session ended.
class _SendError extends StatelessWidget {
  const _SendError(
      {required this.error,
      required this.returnTo,
      this.actionLabel,
      this.onAction});
  final Object error;
  final int returnTo;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: KoloInlineState(
          title: 'Not sent',
          message: failureText(error),
          icon: Icons.error_outline,
          actionLabel: needsSignIn(error) ? 'Sign in' : actionLabel,
          onAction: needsSignIn(error)
              ? () => openBusiness(context, 4, returnTo: returnTo)
              : onAction,
        ),
      );
}

// ---- M-118 Ask a question -----------------------------------------------------------------------------------------

class BusinessAskScreen extends StatefulWidget {
  const BusinessAskScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.businessId});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final String businessId;
  @override
  State<BusinessAskScreen> createState() => _BusinessAskScreenState();
}

class _BusinessAskScreenState extends State<BusinessAskScreen> {
  final _body = TextEditingController();
  final _attempt = AttemptKey();
  String? _subject;
  bool _busy = false, _sent = false;
  Object? _error;
  String? _problem;

  @override
  void dispose() {
    _body.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    if (_busy) return;
    final text = _body.text.trim();
    if (_subject == null) {
      setState(() => _problem = 'Choose what your question is about.');
      return;
    }
    if (text.isEmpty) {
      setState(() => _problem = 'Write your question.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _problem = null;
    });
    try {
      final thread = await widget.repository.ask(
          businessId: widget.businessId,
          subject: _subject!,
          body: text,
          key: _attempt.forContent('$_subject|$text'));
      _attempt.reset();
      if (!mounted) return;
      _sent = true;
      notifySuccess(context, 'Question sent');
      _replace(context, BusinessScreens.conversation, entityId: thread.id);
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => UnsavedChangesGuard(
        dirty: !_sent && _body.text.trim().isNotEmpty,
        busy: _busy,
        child: BusinessPage(
          screen: BusinessScreens.ask,
          catalog: widget.catalog,
          title: 'Ask a question',
          showNavigation: false,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              BusinessLoader<BusinessDetail>(
                inline: true,
                load: () => widget.repository.detailCached(widget.businessId),
                builder: (context, detail, reload) => Padding(
                  padding: const EdgeInsets.only(bottom: 16),
                  child: Text('To ${detail.card.name}',
                      style: KoloVibeText.body(16, weight: FontWeight.w700)),
                ),
              ),
              DropdownButtonFormField<String>(
                key: const ValueKey('ask-subject'),
                initialValue: _subject,
                isExpanded: true,
                decoration:
                    const InputDecoration(labelText: 'What is it about?'),
                items: [
                  for (final subject in inquirySubjects)
                    DropdownMenuItem(
                        value: subject.code, child: Text(subject.label)),
                ],
                onChanged: _busy ? null : (v) => setState(() => _subject = v),
              ),
              const SizedBox(height: 16),
              KoloTextField(
                label: 'Your question',
                controller: _body,
                maxLength: 1000,
                maxLines: 5,
                readOnly: _busy,
                helper:
                    'Up to 1000 characters. Only you and the business can read it. Do not include passwords or payment details.',
                onChanged: (_) => setState(() {}),
              ),
              if (_problem != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Text(_problem!,
                      style: KoloVibeText.body(13, color: KoloVibeColors.red)),
                ),
              if (_error != null)
                _SendError(
                  error: _error!,
                  returnTo: BusinessScreens.ask,
                  actionLabel: (_error is Exception &&
                          failureText(_error!).contains('already have an open'))
                      ? 'Open my questions'
                      : null,
                  onAction: () =>
                      _replace(context, BusinessScreens.myInquiries),
                ),
              FilledButton(
                  onPressed: _busy ? null : _send,
                  child: Text(_busy ? 'Sending…' : 'Send question')),
            ],
          ),
        ),
      );
}

// ---- M-119 My questions -------------------------------------------------------------------------------------------

class BusinessMyInquiriesScreen extends StatelessWidget {
  const BusinessMyInquiriesScreen(
      {super.key, required this.repository, required this.catalog});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.myInquiries,
        catalog: catalog,
        title: 'My questions',
        scroll: false,
        child: BusinessPagedList<CustomerInquiry>(
          onSignIn: () =>
              openBusiness(context, 4, returnTo: BusinessScreens.myInquiries),
          fetch: (cursor) => repository.myInquiries(cursor: cursor),
          empty: KoloInlineState(
            title: 'No questions yet',
            message: 'Questions you send to businesses appear here.',
            icon: Icons.forum_outlined,
            actionLabel: 'Find a business',
            onAction: () => _go(context, BusinessScreens.results),
          ),
          itemBuilder: (context, inquiry) => KoloListRow(
            title: inquiry.businessName,
            subtitle: [
              if (inquiry.subjectCode != null)
                labelFor(inquirySubjects, inquiry.subjectCode!),
              inquiryStateLabel(inquiry.state),
              dateLabel(inquiry.createdAt),
            ].join(' · '),
            onTap: () => _go(context, BusinessScreens.conversation,
                entityId: inquiry.id),
          ),
        ),
      );
}

// ---- M-120 Conversation -------------------------------------------------------------------------------------------

class BusinessConversationScreen extends StatelessWidget {
  const BusinessConversationScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.threadId});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final String threadId;

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.conversation,
        catalog: catalog,
        title: 'Conversation',
        showNavigation: false,
        child: BusinessLoader<CustomerInquiry>(
          onSignIn: () =>
              openBusiness(context, 4, returnTo: BusinessScreens.myInquiries),
          load: () => repository.inquiry(threadId),
          builder: (context, inquiry, reload) =>
              _Conversation(repository: repository, initial: inquiry),
        ),
      );
}

class _Conversation extends StatefulWidget {
  const _Conversation({required this.repository, required this.initial});
  final LiveBusinessRepository repository;
  final CustomerInquiry initial;
  @override
  State<_Conversation> createState() => _ConversationState();
}

class _ConversationState extends State<_Conversation> {
  late CustomerInquiry _inquiry = widget.initial;
  final _reply = TextEditingController();
  final _sendKey = AttemptKey(),
      _closeKey = AttemptKey(),
      _confirmKey = AttemptKey();
  bool _busy = false;
  Object? _error;

  @override
  void dispose() {
    _reply.dispose();
    super.dispose();
  }

  Future<void> _run(Future<CustomerInquiry> Function() action,
      {VoidCallback? onDone}) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final answer = await action();
      if (!mounted) return;
      // Closing and confirming answer without the messages; keep the ones already shown.
      final next = answer.messages.isEmpty
          ? CustomerInquiry(
              answer.id,
              answer.businessId,
              answer.businessName,
              answer.state,
              answer.subjectCode,
              answer.createdAt,
              answer.confirmed,
              _inquiry.messages)
          : answer;
      setState(() => _inquiry = next);
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
        () => widget.repository.sendMessage(_inquiry.id, text,
            key: _sendKey.forContent(text)), onDone: () {
      _sendKey.reset();
      _reply.clear();
    });
  }

  Future<void> _close() async {
    final ok = await confirmDestructive(context,
        title: 'Close this conversation?',
        message:
            'Nobody can send more messages once it is closed. This cannot be undone.',
        confirmLabel: 'Close conversation');
    if (!ok || !mounted) return;
    await _run(() => widget.repository
        .closeInquiry(_inquiry.id, key: _closeKey.forContent('close')));
  }

  Future<void> _confirm() => _run(() => widget.repository
      .confirmInquiry(_inquiry.id, key: _confirmKey.forContent('confirm')));

  @override
  Widget build(BuildContext context) {
    final inquiry = _inquiry;
    final open = inquiry.state == InquiryState.open;
    final both = inquiry.confirmed.customer && inquiry.confirmed.business;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(inquiry.businessName,
            style: KoloVibeText.heading(20, height: 1.2)),
        const SizedBox(height: 4),
        Text(
            [
              if (inquiry.subjectCode != null)
                labelFor(inquirySubjects, inquiry.subjectCode!),
              inquiryStateLabel(inquiry.state),
            ].join(' · '),
            style: KoloVibeText.body(13)),
        const SizedBox(height: 16),
        for (final message in inquiry.messages) _bubble(message),
        if (!open)
          const Padding(
            padding: EdgeInsets.only(bottom: 12),
            child: KoloNote(
                title: 'This conversation is closed',
                message: 'No more messages can be sent.',
                icon: Icons.lock_outline),
          ),
        if (_error != null)
          _SendError(error: _error!, returnTo: BusinessScreens.myInquiries),
        if (open) ...[
          KoloTextField(
            label: 'Your message',
            controller: _reply,
            maxLength: 1000,
            maxLines: 3,
            readOnly: _busy,
          ),
          FilledButton(
              onPressed: _busy ? null : _send,
              child: Text(_busy ? 'Please wait…' : 'Send message')),
          const SizedBox(height: 16),
        ],
        const KoloSectionHeading(title: 'When you are done'),
        const SizedBox(height: 8),
        Text(
            'You confirmed: ${inquiry.confirmed.customer ? 'yes' : 'not yet'}'
            ' · The business confirmed: ${inquiry.confirmed.business ? 'yes' : 'not yet'}',
            style: KoloVibeText.body(13)),
        const SizedBox(height: 4),
        const Text(
            'If you and the business dealt with each other, both of you can confirm it. Once both have, you can write a review based on this conversation.'),
        const SizedBox(height: 8),
        if (open && !inquiry.confirmed.customer)
          OutlinedButton(
              onPressed: _busy ? null : _confirm,
              child: const Text('We dealt with each other')),
        if (both)
          FilledButton(
              onPressed: () => _go(context, BusinessScreens.writeReview,
                  entityId:
                      ReviewTarget(inquiry.businessId, inquiry.id).encoded),
              child: const Text('Write a review')),
        if (open)
          TextButton(
              onPressed: _busy ? null : _close,
              child: const Text('Close conversation')),
        TextButton(
            onPressed: () => _go(context, BusinessScreens.detail,
                entityId: inquiry.businessId),
            child: const Text('View business')),
      ],
    );
  }

  Widget _bubble(InquiryMessage message) {
    final mine = !message.fromBusiness;
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
            Text(mine ? 'You' : _businessName,
                style: KoloVibeText.body(11, weight: FontWeight.w700)),
            const SizedBox(height: 2),
            Text(message.removed ? 'This message was removed.' : message.body!,
                style: KoloVibeText.body(14, height: 1.4)),
            const SizedBox(height: 4),
            Text(dateLabel(message.createdAt), style: KoloVibeText.body(11)),
            if (!message.removed)
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

  String get _businessName => _inquiry.businessName;
}

// ---- M-121 Write a review -----------------------------------------------------------------------------------------

class BusinessWriteReviewScreen extends StatefulWidget {
  const BusinessWriteReviewScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.target});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final ReviewTarget target;
  @override
  State<BusinessWriteReviewScreen> createState() =>
      _BusinessWriteReviewScreenState();
}

class _BusinessWriteReviewScreenState extends State<BusinessWriteReviewScreen> {
  final _title = TextEditingController();
  final _body = TextEditingController();
  final _code = TextEditingController();
  final _attempt = AttemptKey();
  int _rating = 0;
  bool _useCode = false, _busy = false, _done = false;
  Object? _error;
  String? _problem;

  @override
  void dispose() {
    _title.dispose();
    _body.dispose();
    _code.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_busy) return;
    final body = _body.text.trim();
    if (_rating == 0) {
      setState(() => _problem = 'Choose a rating from 1 to 5.');
      return;
    }
    if (body.length < 10) {
      setState(
          () => _problem = 'Write at least 10 characters about your visit.');
      return;
    }
    final code = _useCode ? _code.text.trim() : '';
    if (_useCode && code.length < 16) {
      setState(() => _problem = 'Enter the whole invitation code.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _problem = null;
    });
    try {
      final review = await widget.repository.writeReview(
          businessId: widget.target.businessId,
          rating: _rating,
          title: _title.text,
          body: body,
          interactionThreadId: _useCode ? null : widget.target.threadId,
          invitationCode: _useCode ? code : null,
          key: _attempt.forContent('$_rating|${_title.text}|$body|$code'));
      _attempt.reset();
      if (!mounted) return;
      _done = true;
      notifySuccess(
          context,
          review.state == ReviewState.published
              ? 'Review published'
              : 'Review received. It will appear once it has been checked.');
      _replace(context, BusinessScreens.myReviews);
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => UnsavedChangesGuard(
        dirty: !_done && (_rating > 0 || _body.text.trim().isNotEmpty),
        busy: _busy,
        child: BusinessPage(
          screen: BusinessScreens.writeReview,
          catalog: widget.catalog,
          title: 'Write a review',
          showNavigation: false,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              BusinessLoader<BusinessDetail>(
                inline: true,
                load: () =>
                    widget.repository.detailCached(widget.target.businessId),
                builder: (context, detail, reload) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Text(detail.card.name,
                      style: KoloVibeText.body(16, weight: FontWeight.w700)),
                ),
              ),
              if (widget.target.threadId != null && !_useCode)
                const Padding(
                  padding: EdgeInsets.only(bottom: 12),
                  child: KoloNote(
                      title: 'Based on your conversation',
                      message:
                          'KoloVibe checks that you and the business both confirmed this conversation. The review will say so.',
                      icon: Icons.forum_outlined),
                ),
              Text('Your rating',
                  style: KoloVibeText.body(12,
                      weight: FontWeight.w600, color: KoloVibeColors.navy)),
              const SizedBox(height: 8),
              Wrap(spacing: 8, children: [
                for (var star = 1; star <= 5; star++)
                  Semantics(
                    label: '$star out of 5',
                    selected: _rating == star,
                    button: true,
                    excludeSemantics: true,
                    child: ChoiceChip(
                      key: ValueKey('rating-$star'),
                      label: Text('$star ★'),
                      selected: _rating == star,
                      onSelected:
                          _busy ? null : (_) => setState(() => _rating = star),
                    ),
                  ),
              ]),
              const SizedBox(height: 16),
              KoloTextField(
                  label: 'Title (optional)',
                  controller: _title,
                  maxLength: 100,
                  readOnly: _busy),
              KoloTextField(
                label: 'Your review',
                controller: _body,
                maxLength: 2000,
                maxLines: 6,
                readOnly: _busy,
                helper:
                    'At least 10 characters. Reviews are public and show a label such as “Reviewer 3”, not your name.',
                onChanged: (_) => setState(() {}),
              ),
              SwitchListTile(
                key: const ValueKey('review-use-code'),
                contentPadding: EdgeInsets.zero,
                title: const Text('I have an invitation code'),
                subtitle: const Text(
                    'A business can invite you to review it with a one-time code.'),
                value: _useCode,
                onChanged: _busy ? null : (v) => setState(() => _useCode = v),
              ),
              if (_useCode)
                KoloTextField(
                    label: 'Invitation code',
                    controller: _code,
                    maxLength: 64,
                    readOnly: _busy),
              if (_problem != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Text(_problem!,
                      style: KoloVibeText.body(13, color: KoloVibeColors.red)),
                ),
              if (_error != null)
                _SendError(
                  error: _error!,
                  returnTo: BusinessScreens.writeReview,
                  actionLabel: failureText(_error!).contains('already reviewed')
                      ? 'Open my reviews'
                      : null,
                  onAction: () => _replace(context, BusinessScreens.myReviews),
                ),
              FilledButton(
                  onPressed: _busy ? null : _submit,
                  child: Text(_busy ? 'Sending…' : 'Submit review')),
            ],
          ),
        ),
      );
}

// ---- M-122 My reviews ---------------------------------------------------------------------------------------------

class BusinessMyReviewsScreen extends StatefulWidget {
  const BusinessMyReviewsScreen(
      {super.key, required this.repository, required this.catalog});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  @override
  State<BusinessMyReviewsScreen> createState() =>
      _BusinessMyReviewsScreenState();
}

class _BusinessMyReviewsScreenState extends State<BusinessMyReviewsScreen> {
  int _generation = 0;

  Future<void> _open(int screen, String id) async {
    final route = ScreenRoute(screen, entityId: id);
    await Navigator.of(context)
        .pushNamed<Object?>(route.name, arguments: route);
    if (mounted) setState(() => _generation++);
  }

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.myReviews,
        catalog: widget.catalog,
        title: 'My reviews',
        scroll: false,
        child: BusinessPagedList<OwnReview>(
          key: ValueKey(_generation),
          onSignIn: () =>
              openBusiness(context, 4, returnTo: BusinessScreens.myReviews),
          fetch: (cursor) => widget.repository.myReviews(cursor: cursor),
          empty: KoloInlineState(
            title: 'No reviews yet',
            message: 'Reviews you write appear here.',
            icon: Icons.rate_review_outlined,
            actionLabel: 'Find a business',
            onAction: () => _go(context, BusinessScreens.results),
          ),
          itemBuilder: (context, review) => _OwnReviewTile(
            review: review,
            onView: () => _go(context, BusinessScreens.detail,
                entityId: review.businessId),
            onEdit: () => _open(BusinessScreens.editReview, review.id),
            onWithdraw: () => _open(BusinessScreens.withdrawReview, review.id),
          ),
        ),
      );
}

class _OwnReviewTile extends StatelessWidget {
  const _OwnReviewTile(
      {required this.review,
      required this.onView,
      required this.onEdit,
      required this.onWithdraw});
  final OwnReview review;
  final VoidCallback onView, onEdit, onWithdraw;

  @override
  Widget build(BuildContext context) {
    final active = review.state == ReviewState.published ||
        review.state == ReviewState.held;
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
              Wrap(
                  spacing: 12,
                  runSpacing: 8,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    Semantics(
                      label: 'Rating ${starsLabel(review.rating)}',
                      excludeSemantics: true,
                      child: Text(
                          '${'★' * review.rating}${'☆' * (5 - review.rating)}',
                          style: KoloVibeText.body(18,
                              color: KoloVibeColors.gold)),
                    ),
                    KoloBadge(reviewStateLabel(review.state)),
                  ]),
              if (review.title != null) ...[
                const SizedBox(height: 4),
                Text(review.title!,
                    style: KoloVibeText.body(15, weight: FontWeight.w700)),
              ],
              const SizedBox(height: 4),
              Text(review.body, style: KoloVibeText.body(14, height: 1.4)),
              const SizedBox(height: 8),
              Text(
                  '${dateLabel(review.createdAt)}'
                  '${review.editedAt == null ? '' : ' · edited'}'
                  ' · ${reviewBasisLabel(review.basis)}',
                  style: KoloVibeText.body(12)),
              if (review.state == ReviewState.held)
                const Padding(
                  padding: EdgeInsets.only(top: 8),
                  child: Text(
                      'This review is waiting for a check before it is shown to others.'),
                ),
              if (review.state == ReviewState.removed)
                const Padding(
                  padding: EdgeInsets.only(top: 8),
                  child: Text('This review was removed by KoloVibe reviewers.'),
                ),
              Wrap(children: [
                TextButton(
                    onPressed: onView, child: const Text('View business')),
                if (active)
                  TextButton(onPressed: onEdit, child: const Text('Edit')),
                if (active)
                  TextButton(
                      onPressed: onWithdraw, child: const Text('Withdraw')),
              ]),
            ],
          ),
        ),
      ),
    );
  }
}

// ---- M-123 Edit review --------------------------------------------------------------------------------------------

class BusinessEditReviewScreen extends StatelessWidget {
  const BusinessEditReviewScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.reviewId});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final String reviewId;

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.editReview,
        catalog: catalog,
        title: 'Edit review',
        showNavigation: false,
        child: BusinessLoader<OwnReview?>(
          onSignIn: () =>
              openBusiness(context, 4, returnTo: BusinessScreens.myReviews),
          load: () => repository.findOwnReview(reviewId),
          builder: (context, review, reload) => review == null
              ? const KoloInlineState(
                  title: 'Review not found',
                  message: 'This review is no longer available.',
                  icon: Icons.search_off)
              : _EditReviewForm(repository: repository, review: review),
        ),
      );
}

class _EditReviewForm extends StatefulWidget {
  const _EditReviewForm({required this.repository, required this.review});
  final LiveBusinessRepository repository;
  final OwnReview review;
  @override
  State<_EditReviewForm> createState() => _EditReviewFormState();
}

class _EditReviewFormState extends State<_EditReviewForm> {
  late final _title = TextEditingController(text: widget.review.title ?? '');
  late final _body = TextEditingController(text: widget.review.body);
  final _attempt = AttemptKey();
  late int _rating = widget.review.rating;
  bool _busy = false, _done = false;
  Object? _error;
  String? _problem;

  @override
  void dispose() {
    _title.dispose();
    _body.dispose();
    super.dispose();
  }

  bool get _changed =>
      _rating != widget.review.rating ||
      _title.text.trim() != (widget.review.title ?? '') ||
      _body.text.trim() != widget.review.body;

  Future<void> _save() async {
    if (_busy) return;
    final body = _body.text.trim();
    if (body.length < 10) {
      setState(() => _problem = 'Write at least 10 characters.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _problem = null;
    });
    final title = _title.text.trim();
    try {
      await widget.repository.editReview(widget.review.id,
          rating: _rating == widget.review.rating ? null : _rating,
          title: title == (widget.review.title ?? '') ? null : title,
          body: body == widget.review.body ? null : body,
          key: _attempt.forContent('$_rating|$title|$body'));
      _attempt.reset();
      if (!mounted) return;
      _done = true;
      notifySuccess(context, 'Review updated');
      Navigator.of(context).pop(true);
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => UnsavedChangesGuard(
        dirty: !_done && _changed,
        busy: _busy,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Wrap(spacing: 8, children: [
              for (var star = 1; star <= 5; star++)
                ChoiceChip(
                  key: ValueKey('rating-$star'),
                  label: Text('$star ★'),
                  selected: _rating == star,
                  onSelected:
                      _busy ? null : (_) => setState(() => _rating = star),
                ),
            ]),
            const SizedBox(height: 16),
            KoloTextField(
                label: 'Title (optional)',
                controller: _title,
                maxLength: 100,
                readOnly: _busy,
                onChanged: (_) => setState(() {})),
            KoloTextField(
                label: 'Your review',
                controller: _body,
                maxLength: 2000,
                maxLines: 6,
                readOnly: _busy,
                onChanged: (_) => setState(() {})),
            if (_problem != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(_problem!,
                    style: KoloVibeText.body(13, color: KoloVibeColors.red)),
              ),
            if (_error != null)
              _SendError(error: _error!, returnTo: BusinessScreens.myReviews),
            FilledButton(
                onPressed: _busy || !_changed ? null : _save,
                child: Text(_busy ? 'Saving…' : 'Save changes')),
          ],
        ),
      );
}

// ---- M-124 Withdraw review ----------------------------------------------------------------------------------------

class BusinessWithdrawReviewScreen extends StatefulWidget {
  const BusinessWithdrawReviewScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.reviewId});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final String reviewId;
  @override
  State<BusinessWithdrawReviewScreen> createState() =>
      _BusinessWithdrawReviewScreenState();
}

class _BusinessWithdrawReviewScreenState
    extends State<BusinessWithdrawReviewScreen> {
  final _attempt = AttemptKey();
  bool _busy = false;
  Object? _error;

  Future<void> _withdraw() async {
    if (_busy) return;
    final ok = await confirmDestructive(context,
        title: 'Withdraw this review?',
        message:
            'It will no longer be shown on the business page. You cannot undo this.',
        confirmLabel: 'Withdraw review');
    if (!ok || !mounted) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.repository.withdrawReview(widget.reviewId,
          key: _attempt.forContent('withdraw'));
      if (!mounted) return;
      notifySuccess(context, 'Review withdrawn');
      Navigator.of(context).pop(true);
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: BusinessScreens.withdrawReview,
        catalog: widget.catalog,
        title: 'Withdraw review',
        showNavigation: false,
        child: BusinessLoader<OwnReview?>(
          onSignIn: () =>
              openBusiness(context, 4, returnTo: BusinessScreens.myReviews),
          load: () => widget.repository.findOwnReview(widget.reviewId),
          builder: (context, review, reload) {
            if (review == null) {
              return const KoloInlineState(
                  title: 'Review not found',
                  message: 'This review is no longer available.',
                  icon: Icons.search_off);
            }
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('${review.rating} out of 5',
                    style: KoloVibeText.body(16, weight: FontWeight.w700)),
                if (review.title != null) Text(review.title!),
                const SizedBox(height: 4),
                Text(review.body),
                const SizedBox(height: 16),
                const KoloNote(
                    title: 'Withdrawing hides your review',
                    message:
                        'It stops being shown on the business page. The business may still see that you reviewed it.',
                    icon: Icons.visibility_off_outlined),
                const SizedBox(height: 12),
                if (_error != null)
                  _SendError(
                      error: _error!, returnTo: BusinessScreens.myReviews),
                FilledButton(
                    onPressed: _busy ? null : _withdraw,
                    child: Text(_busy ? 'Please wait…' : 'Withdraw my review')),
                TextButton(
                    onPressed: _busy ? null : () => Navigator.of(context).pop(),
                    child: const Text('Keep my review')),
              ],
            );
          },
        ),
      );
}

// ---- M-125 Report -------------------------------------------------------------------------------------------------

class BusinessReportScreen extends StatefulWidget {
  const BusinessReportScreen(
      {super.key,
      required this.repository,
      required this.catalog,
      required this.target});
  final LiveBusinessRepository repository;
  final DesignCatalog catalog;
  final ReportTarget target;
  @override
  State<BusinessReportScreen> createState() => _BusinessReportScreenState();
}

class _BusinessReportScreenState extends State<BusinessReportScreen> {
  final _details = TextEditingController();
  final _attempt = AttemptKey();
  String? _reason;
  bool _busy = false, _sent = false;
  Object? _error;
  String? _problem;

  @override
  void dispose() {
    _details.dispose();
    super.dispose();
  }

  String get _what => switch (widget.target.type) {
        'review' => 'review',
        'review_response' => 'reply',
        _ => 'message',
      };

  Future<void> _submit() async {
    if (_busy) return;
    if (_reason == null) {
      setState(() => _problem = 'Choose a reason.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _problem = null;
    });
    try {
      await widget.repository.report(
          subjectType: widget.target.type,
          subjectId: widget.target.id,
          reason: _reason!,
          details: _details.text,
          key: _attempt.forContent('$_reason|${_details.text.trim()}'));
      _attempt.reset();
      if (mounted) setState(() => _sent = true);
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => UnsavedChangesGuard(
        dirty: !_sent && (_reason != null || _details.text.trim().isNotEmpty),
        busy: _busy,
        child: BusinessPage(
          screen: BusinessScreens.report,
          catalog: widget.catalog,
          title: 'Report this $_what',
          showNavigation: false,
          child: _sent ? _thanks(context) : _form(context),
        ),
      );

  Widget _thanks(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const KoloNote(
              title: 'Report received',
              message:
                  'Thank you. KoloVibe reviewers will look at it. Reporting something does not remove it straight away.',
              tone: KoloNoteTone.success,
              icon: Icons.check_circle_outline),
          const SizedBox(height: 16),
          FilledButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Done')),
        ],
      );

  Widget _form(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Why are you reporting this $_what?',
              style: KoloVibeText.body(15, weight: FontWeight.w700)),
          const SizedBox(height: 8),
          Wrap(spacing: 8, runSpacing: 8, children: [
            for (final reason in reportReasons)
              ChoiceChip(
                key: ValueKey('reason-${reason.code}'),
                label: Text(reason.label),
                selected: _reason == reason.code,
                onSelected:
                    _busy ? null : (_) => setState(() => _reason = reason.code),
              ),
          ]),
          const SizedBox(height: 16),
          KoloTextField(
            label: 'More detail (optional)',
            controller: _details,
            maxLength: 1000,
            maxLines: 4,
            readOnly: _busy,
            onChanged: (_) => setState(() {}),
          ),
          if (_problem != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(_problem!,
                  style: KoloVibeText.body(13, color: KoloVibeColors.red)),
            ),
          if (_error != null)
            _SendError(error: _error!, returnTo: BusinessScreens.report),
          FilledButton(
              onPressed: _busy ? null : _submit,
              child: Text(_busy ? 'Sending…' : 'Send report')),
        ],
      );
}
