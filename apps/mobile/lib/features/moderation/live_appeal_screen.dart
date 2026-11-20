import 'package:flutter/material.dart';
import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import '../../core/presentation/design_node.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/state/async_resource.dart';
import '../../shared/widgets/kolo_components.dart';
import '../../shared/widgets/live_state_view.dart';
import '../creators/creator_shell.dart';
import 'live_moderation_repository.dart';
import 'live_standing_repository.dart';
import 'notice_copy.dart';

/// M-078 Appeal / review request for one of the creator's own videos.
///
/// Whether a review may be requested is the server's `appealable` answer on the
/// notice and is never inferred. The approved export draws the "availability
/// not confirmed" state. The eligible states (statement entry, validation,
/// sending, failure and receipt) follow the new frames on the Figma page "R1
/// adaptations (pending owner review)" and are NOT visually approved until the
/// owner reviews them. They appear only when the server says the decision is
/// appealable and no request exists; the server also enforces ownership and one
/// request per decision.
class LiveAppealScreen extends StatefulWidget {
  const LiveAppealScreen(
      {super.key,
      required this.route,
      required this.catalog,
      required this.standing,
      required this.moderation});
  final ScreenRoute route;
  final DesignCatalog catalog;
  final LiveStandingRepository standing;
  final LiveModerationRepository moderation;

  @override
  State<LiveAppealScreen> createState() => _LiveAppealScreenState();
}

class _LiveAppealScreenState extends State<LiveAppealScreen> {
  AsyncResource<VideoNotice>? resource;
  final statement = TextEditingController();
  final form = GlobalKey<FormState>();
  bool sending = false;
  Object? sendFailure;
  ModerationReceipt? receipt;
  bool get sent => receipt != null;

  String? get videoId => widget.route.entityId;

  @override
  void initState() {
    super.initState();
    final id = videoId;
    if (id != null && isApiId(id)) {
      resource = AsyncResource<VideoNotice>(() => widget.standing.notice(id),
          unreadable: 'This notice could not be read. Try again.')
        ..load();
    }
  }

  @override
  void dispose() {
    resource?.dispose();
    statement.dispose();
    super.dispose();
  }

  void _open(int screen, {String? entityId}) =>
      openCreatorScreen(context, screen, entityId: entityId);

  Future<void> _send() async {
    // The server's answer on the notice is the only authority; never submit without it.
    final notice = resource?.value;
    if (sending ||
        notice == null ||
        !notice.appealable ||
        notice.appeal != null ||
        receipt != null ||
        !(form.currentState?.validate() ?? false)) {
      return;
    }
    setState(() {
      sending = true;
      sendFailure = null;
    });
    try {
      final result = await widget.moderation
          .appeal(videoId: videoId!, reason: statement.text.trim());
      if (!mounted) return;
      statement.clear();
      setState(() => receipt = result);
      await resource!.load();
    } catch (failure) {
      if (mounted) setState(() => sendFailure = failure);
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }

  String _failureText(Object failure) {
    if (failure is ApiFailure) {
      if (failure.status == 409) {
        return 'A review request already exists for this decision.';
      }
      if (failure.status == 403) {
        return 'A review request is not available for this decision.';
      }
      if (failure.kind == FailureKind.offline) {
        return 'Check your connection, then try again. Your statement is kept.';
      }
      if (failure.status == 401) {
        return 'Sign in again to send your review request.';
      }
    }
    return 'The review request could not be sent. Your statement is kept. Try again.';
  }

  /// The receipt shows what the server returned, never a guess: id, status and time.
  Widget _receipt(BuildContext context, ModerationReceipt done) {
    final sentAt = done.createdAt.toUtc();
    const months = [
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
      'Dec'
    ];
    return SingleChildScrollView(
      key: const ValueKey('appeal-receipt'),
      padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const KoloMedallion(KoloIcons.circleCheck),
        const SizedBox(height: 20),
        const KoloHeadline('Review request received.', size: 26),
        const SizedBox(height: 12),
        Text(
            'A reviewer who was not part of the first decision will read your statement.',
            style: KoloVibeText.body(14, height: 1.5)),
        const SizedBox(height: 16),
        Semantics(
          container: true,
          child: Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(KoloVibeRadii.card),
                border: Border.all(color: KoloVibeColors.line)),
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              for (final (label, value) in [
                ('Request ID', done.id),
                ('Status', appealStatusText(done.status)),
                (
                  'Sent',
                  '${sentAt.day} ${months[sentAt.month - 1]} ${sentAt.year}, ${sentAt.hour.toString().padLeft(2, '0')}:${sentAt.minute.toString().padLeft(2, '0')} UTC'
                ),
              ]) ...[
                Text(label,
                    style: KoloVibeText.body(11, color: KoloVibeColors.muted)),
                const SizedBox(height: 2),
                Text(value,
                    style: KoloVibeText.body(14,
                        weight: FontWeight.w600, color: KoloVibeColors.navy)),
                const SizedBox(height: 12),
              ],
            ]),
          ),
        ),
        const SizedBox(height: 16),
        const KoloNote(
            title: 'What happens next',
            message:
                'The outcome appears on the content notice for this video. You don’t need to send anything else.'),
        FilledButton(
            onPressed: () => _open(76, entityId: videoId),
            child: const Text('Back to content notice')),
      ]),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Appeal / Review Request')),
        body: SafeArea(child: _body(context)),
        bottomNavigationBar: creatorNavigation(context, widget.catalog, 78),
      );

  Widget _body(BuildContext context) {
    final resource = this.resource;
    if (resource == null) {
      return LiveStateView.empty(
          title: 'Choose a video',
          message: 'Open a review request from a content notice.',
          actionLabel: 'Open my video library',
          onAction: () => _open(40));
    }
    return ListenableBuilder(
        listenable: resource,
        builder: (context, _) {
          switch (resource.phase) {
            case ResourcePhase.loading:
              return const LiveStateView.loading(label: 'Loading the notice');
            case ResourcePhase.failed:
              final error = resource.error!;
              if (error is ApiFailure && error.kind == FailureKind.forbidden) {
                return const LiveStateView.empty(
                    title: 'Not available',
                    message:
                        'Review requests are shown only to the creator who owns the video.',
                    icon: Icons.lock_outline);
              }
              return LiveStateView.failure(error,
                  onRetry: resource.load,
                  onSignIn: () => signInThenReturn(context, 37));
            case ResourcePhase.ready:
              return _content(context, resource.value!);
          }
        });
  }

  Widget _content(BuildContext context, VideoNotice notice) {
    final appeal = notice.appeal;
    final local = MaterialLocalizations.of(context);
    final eligible = notice.appealable && appeal == null;
    if (receipt case final done?) return _receipt(context, done);
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
      child: Form(
        key: form,
        child:
            Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          KoloHeadline(
              eligible
                  ? 'Ask for a review.'
                  : 'Review options depend on policy.',
              size: 26),
          const SizedBox(height: 16),
          if (notice.hasDecision)
            KoloNote(
                title: noticeDecisionLabel(notice.decision),
                message: noticeSummary(notice.decision),
                icon: Icons.gavel_outlined),
          if (appeal != null) ...[
            KoloNote(
                title: 'Your review request',
                message:
                    '${appealStatusText(appeal.status)}\nSent ${local.formatMediumDate(appeal.createdAt.toLocal())}\n\n${appeal.reason}',
                icon: Icons.mark_email_read_outlined,
                tone: KoloNoteTone.success),
          ] else if (!eligible) ...[
            const KoloNote(
                title: 'Appeal availability not confirmed',
                message:
                    'A review request can be sent only when the approved moderation policy and this decision allow it.'),
            const KoloNote(
                title: 'Review request unavailable',
                message:
                    'This screen does not submit an appeal. Check the decision notice for permitted next steps.',
                icon: Icons.lock_outline),
          ] else ...[
            const KoloNote(
                title: 'This decision can be reviewed',
                message:
                    'You can send one review request. A reviewer who was not part of the first decision will read your statement.',
                icon: Icons.fact_check_outlined),
            if (sendFailure != null)
              KoloNote(
                  key: const ValueKey('appeal-failure'),
                  title: 'We couldn’t send your request',
                  message: _failureText(sendFailure!),
                  icon: Icons.error_outline,
                  tone: KoloNoteTone.alert),
            KoloTextField(
                key: const ValueKey('Review statement'),
                label: 'Your statement',
                controller: statement,
                hint: 'Explain why the decision should be reviewed',
                helper:
                    'At least 10 characters. Don’t include passwords or other people’s details.',
                readOnly: sending,
                maxLength: 2000,
                maxLines: 5,
                validator: (value) => (value ?? '').trim().length < 10
                    ? 'Write at least 10 characters.'
                    : null),
            FilledButton(
                onPressed: sending ? null : _send,
                child: Text(sending
                    ? 'Sending…'
                    : sendFailure == null
                        ? 'Send review request'
                        : 'Try again')),
            const SizedBox(height: 12),
          ],
          OutlinedButton(
              onPressed: () => _open(76, entityId: videoId),
              child: const Text('Return to content notice')),
          const SizedBox(height: 12),
          OutlinedButton(
              onPressed: () => _open(87),
              child: const Text('Read moderation policy')),
        ]),
      ),
    );
  }
}
