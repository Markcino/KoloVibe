import 'package:flutter/material.dart';
import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import '../../core/presentation/design_node.dart';
import '../../shared/state/async_resource.dart';
import '../../shared/widgets/live_state_view.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/kolo_components.dart';
import '../creators/creator_shell.dart';
import 'live_standing_repository.dart';
import 'notice_copy.dart';

/// M-076 Content restriction notice: the latest applied decision about one of
/// the creator's own videos, its server-recorded reason code and the creator's
/// own review request, if any. Read-only; whether a review may be requested is
/// the server's `appealable` answer and is never inferred.
class LiveNoticeScreen extends StatefulWidget {
  const LiveNoticeScreen(
      {super.key,
      required this.route,
      required this.catalog,
      required this.repository,
      this.resource});
  final ScreenRoute route;
  final DesignCatalog catalog;
  final LiveStandingRepository repository;

  /// Test seam for a pre-built resource.
  final AsyncResource<VideoNotice>? resource;

  @override
  State<LiveNoticeScreen> createState() => _LiveNoticeScreenState();
}

class _LiveNoticeScreenState extends State<LiveNoticeScreen> {
  AsyncResource<VideoNotice>? resource;

  @override
  void initState() {
    super.initState();
    final id = widget.route.entityId;
    resource = widget.resource ??
        (id == null || !isApiId(id)
            ? null
            : AsyncResource<VideoNotice>(() => widget.repository.notice(id),
                unreadable: 'This notice could not be read. Try again.'));
    resource?.load();
  }

  @override
  void dispose() {
    resource?.dispose();
    super.dispose();
  }

  void _open(int screen) => openCreatorScreen(context, screen);

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
            title: Text(widget.route.screen == 57
                ? 'Content status notice'
                : 'Content restriction notice')),
        body: SafeArea(child: _body(context)),
        bottomNavigationBar: creatorNavigation(
            context, widget.catalog, widget.route.screen == 57 ? 57 : 76),
      );

  Widget _body(BuildContext context) {
    final resource = this.resource;
    if (resource == null) {
      return LiveStateView.empty(
          title: 'Choose a video',
          message: 'Open a notice from your video library or account status.',
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
                        'Content notices are shown only to the creator who owns the video.',
                    icon: Icons.lock_outline);
              }
              return LiveStateView.failure(error,
                  onRetry: resource.load,
                  onSignIn: () => signInThenReturn(context, 37));
            case ResourcePhase.ready:
              return _notice(context, resource.value!);
          }
        });
  }

  Widget _notice(BuildContext context, VideoNotice notice) {
    final local = MaterialLocalizations.of(context);
    final date = notice.decidedAt == null
        ? null
        : local.formatMediumDate(notice.decidedAt!.toLocal());
    final appeal = notice.appeal;
    return RefreshIndicator(
      onRefresh: resource!.load,
      child: ListView(
          padding: const EdgeInsets.all(16),
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            const KoloMedallion(KoloIcons.shieldAlert, plain: true),
            const SizedBox(height: 16),
            Semantics(
                header: true,
                child: KoloHeadline(noticeHeadline(notice.decision), size: 26)),
            const SizedBox(height: 12),
            if (notice.hasDecision)
              Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    KoloBadge(noticeDecisionLabel(notice.decision)),
                    Text('Content notice · $date',
                        style: KoloVibeText.body(12)),
                  ]),
            const SizedBox(height: 12),
            KoloNote(
                title: 'About this decision',
                message: noticeSummary(notice.decision),
                asset: KoloIcons.info),
            if (notice.hasDecision)
              KoloCard(
                  title: 'Reason', message: noticeReason(notice.reasonCode)),
            if (appeal != null) ...[
              KoloCard(
                  title: 'Your review request',
                  message:
                      '${appealStatusText(appeal.status)}\nSent ${local.formatMediumDate(appeal.createdAt.toLocal())}'),
              KoloCard(title: 'Your statement', message: appeal.reason),
            ],
            if (notice.appealable && appeal == null) ...[
              const KoloNote(
                  title: 'Review request available',
                  message: 'This decision is eligible for a review request.',
                  asset: KoloIcons.circleCheck,
                  tone: KoloNoteTone.success),
              OutlinedButton(
                  onPressed: () => openCreatorScreen(context, 78,
                      entityId: widget.route.entityId),
                  child: const Text('Request a review')),
              const SizedBox(height: 12),
            ],
            const KoloCard(
                title: 'Next steps',
                message:
                    'Next steps depend on the decision and current moderation policy. Review options appear only when permitted.'),
            FilledButton(
                onPressed: () => _open(87),
                child: const Text('View policy information')),
            const SizedBox(height: 12),
            OutlinedButton(
                onPressed: () => _open(89),
                child: const Text('Help & Support')),
          ]),
    );
  }
}
