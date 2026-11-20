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
/// notice and is never inferred. The Figma export only draws the
/// "availability not confirmed" state; the eligible form (a statement and a
/// submit action to `POST /videos/{id}/appeals`) is a proposed state that the
/// design owner has not approved, so it appears only when the server allows it.
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
  bool sent = false;

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
    if (sending || !(form.currentState?.validate() ?? false)) return;
    setState(() {
      sending = true;
      sendFailure = null;
    });
    try {
      await widget.moderation
          .appeal(videoId: videoId!, reason: statement.text.trim());
      if (!mounted) return;
      statement.clear();
      setState(() => sent = true);
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
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
      child: Form(
        key: form,
        child:
            Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          const KoloHeadline('Review options depend on policy.', size: 26),
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
                title: 'This decision is eligible for review',
                message: 'Explain why the decision should be reviewed.',
                icon: Icons.fact_check_outlined),
            KoloTextField(
                key: const ValueKey('Review statement'),
                label: 'Review statement',
                controller: statement,
                hint: 'Explain why the decision should be reviewed',
                maxLength: 2000,
                maxLines: 5,
                validator: (value) => (value ?? '').trim().length < 10
                    ? 'Write at least 10 characters.'
                    : null),
            if (sendFailure != null)
              Semantics(
                  liveRegion: true,
                  child: Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Text(_failureText(sendFailure!),
                          style: KoloVibeText.body(12,
                              color: KoloVibeColors.red)))),
            FilledButton(
                onPressed: sending ? null : _send,
                child: Text(sending ? 'Sending…' : 'Send review request')),
            const SizedBox(height: 12),
          ],
          if (sent && appeal != null) const SizedBox(height: 4),
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
