import 'package:flutter/material.dart';
import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import '../../core/presentation/design_node.dart';
import '../../shared/state/async_resource.dart';
import '../../shared/widgets/live_state_view.dart';
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
        appBar: AppBar(title: const Text('Content restriction notice')),
        body: SafeArea(child: _body(context)),
        bottomNavigationBar: creatorNavigation(context, widget.catalog, 76),
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
    final text = Theme.of(context).textTheme;
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
            Semantics(
                header: true,
                child: Text(noticeHeadline(notice.decision),
                    style: text.headlineMedium)),
            const SizedBox(height: 8),
            if (notice.hasDecision)
              Row(children: [
                Chip(label: Text(noticeDecisionLabel(notice.decision))),
                const SizedBox(width: 8),
                Flexible(child: Text('Content notice · $date')),
              ]),
            const SizedBox(height: 8),
            Text(noticeSummary(notice.decision)),
            if (notice.hasDecision) ...[
              const SizedBox(height: 16),
              Text('Reason', style: text.titleMedium),
              Text(noticeReason(notice.reasonCode)),
            ],
            if (appeal != null) ...[
              const SizedBox(height: 16),
              Text('Your review request', style: text.titleMedium),
              Text(appealStatusText(appeal.status)),
              Text(
                  'Sent ${local.formatMediumDate(appeal.createdAt.toLocal())}'),
              const SizedBox(height: 8),
              Card(
                  child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Text(appeal.reason))),
            ],
            if (notice.appealable) ...[
              const SizedBox(height: 8),
              const Card(
                  child: Padding(
                      padding: EdgeInsets.all(16),
                      child: Text(
                          'This decision is eligible for a review request. Sending a review request is not available in the app yet.'))),
            ],
            const SizedBox(height: 16),
            const Text(
                'Next steps depend on the decision and current moderation policy. Review options appear only when permitted.'),
            const SizedBox(height: 8),
            TextButton(
                onPressed: () => _open(87),
                child: const Text('View policy information')),
            TextButton(
                onPressed: () => _open(89),
                child: const Text('Help & Support')),
          ]),
    );
  }
}
