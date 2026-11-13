import 'package:flutter/material.dart';
import '../../core/presentation/design_node.dart';
import '../../shared/state/async_resource.dart';
import '../../shared/widgets/live_state_view.dart';
import '../creators/creator_shell.dart';
import 'live_standing_repository.dart';
import 'notice_copy.dart';
import 'standing_controller.dart';

/// M-077 Account status: the server's live account and creator standing, and
/// the creator's recent content notices. Read-only.
///
/// The standing read has no account-level notice, so no "account notice" is
/// offered; only per-video notices (M-076) exist.
class LiveStandingScreen extends StatefulWidget {
  const LiveStandingScreen(
      {super.key,
      required this.catalog,
      required this.repository,
      this.titleLookup,
      this.controller});
  final DesignCatalog catalog;
  final LiveStandingRepository repository;
  final Future<Map<String, String>> Function(Set<String> ids)? titleLookup;
  final StandingController? controller;

  @override
  State<LiveStandingScreen> createState() => _LiveStandingScreenState();
}

class _LiveStandingScreenState extends State<LiveStandingScreen> {
  late final StandingController controller;

  @override
  void initState() {
    super.initState();
    controller = widget.controller ??
        StandingController(widget.repository, titleLookup: widget.titleLookup);
    controller.load();
  }

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  void _open(int screen, {String? entityId}) =>
      openCreatorScreen(context, screen, entityId: entityId);

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Account status')),
        body: SafeArea(
            child: ListenableBuilder(
                listenable: controller,
                builder: (context, _) => _body(context))),
        bottomNavigationBar: creatorNavigation(context, widget.catalog, 77),
      );

  Widget _body(BuildContext context) {
    final resource = controller.standing;
    switch (resource.phase) {
      case ResourcePhase.loading:
        return const LiveStateView.loading(
            label: 'Loading your account status');
      case ResourcePhase.failed:
        return LiveStateView.failure(resource.error!,
            onRetry: controller.load,
            onSignIn: () => signInThenReturn(context, 77));
      case ResourcePhase.ready:
        return _standing(context, resource.value!);
    }
  }

  Widget _standing(BuildContext context, AccountStanding standing) {
    final text = Theme.of(context).textTheme;
    final copy = standingCopy(standing);
    final local = MaterialLocalizations.of(context);
    return RefreshIndicator(
      onRefresh: controller.load,
      child: ListView(
          padding: const EdgeInsets.all(16),
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            Semantics(
                header: true,
                child: Text(copy.headline, style: text.headlineMedium)),
            const SizedBox(height: 8),
            Text(copy.body),
            const SizedBox(height: 16),
            Card(
                child: ListTile(
                    leading: Icon(standing.publishingAllowed
                        ? Icons.check_circle_outline
                        : Icons.block_outlined),
                    title: Text(standing.publishingAllowed
                        ? 'Publishing is available'
                        : 'Publishing is unavailable'),
                    subtitle: Text(copy.publishing))),
            if (standing.creatorStatus == null)
              FilledButton(
                  onPressed: () => _open(36),
                  child: const Text('Become a creator')),
            if (standing.creatorStatus != null) ...[
              const SizedBox(height: 16),
              Semantics(
                  header: true,
                  child: Text('Content notices', style: text.titleMedium)),
              if (standing.notices.isEmpty)
                const ListTile(title: Text('No content notices.')),
              for (final notice in standing.notices)
                Card(
                    child: ListTile(
                  title: Text(
                      controller.titles[notice.videoId] ?? 'Content notice'),
                  subtitle: Text([
                    noticeDecisionLabel(notice.decision),
                    if (notice.decidedAt != null)
                      local.formatMediumDate(notice.decidedAt!.toLocal()),
                  ].join(' · ')),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => _open(76, entityId: notice.videoId),
                )),
            ],
            const SizedBox(height: 16),
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
