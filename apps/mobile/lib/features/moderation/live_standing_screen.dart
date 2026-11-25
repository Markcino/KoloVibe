import 'package:flutter/material.dart';
import '../../core/presentation/design_node.dart';
import '../../shared/state/async_resource.dart';
import '../../shared/widgets/live_state_view.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/kolo_components.dart';
import '../creators/creator_shell.dart';
import 'live_restriction_repository.dart';
import 'live_standing_repository.dart';
import 'measures_section.dart';
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
      this.restrictions,
      this.titleLookup,
      this.controller});
  final DesignCatalog catalog;
  final LiveStandingRepository repository;

  /// Decision F: the creator's own measures; omitted, the section is not shown.
  final LiveRestrictionRepository? restrictions;
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
    final copy = standingCopy(standing);
    final local = MaterialLocalizations.of(context);
    return RefreshIndicator(
      onRefresh: controller.load,
      child: ListView(
          padding: const EdgeInsets.all(16),
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            KoloMedallion(standing.publishingAllowed
                ? KoloIcons.shieldCheck
                : KoloIcons.shieldBan),
            const SizedBox(height: 24),
            Semantics(
                header: true, child: KoloHeadline(copy.headline, size: 26)),
            const SizedBox(height: 12),
            Text(copy.body, style: KoloVibeText.body(14, height: 1.5)),
            const SizedBox(height: 16),
            KoloNote(
                title: standing.publishingAllowed
                    ? 'Publishing is available'
                    : 'Publishing is unavailable',
                message: copy.publishing,
                asset: standing.publishingAllowed
                    ? KoloIcons.circleCheck
                    : KoloIcons.circleAlert,
                tone: standing.publishingAllowed
                    ? KoloNoteTone.success
                    : KoloNoteTone.alert),
            if (standing.creatorStatus == null)
              FilledButton(
                  onPressed: () => _open(36),
                  child: const Text('Become a creator')),
            if (standing.creatorStatus != null) ...[
              const SizedBox(height: 16),
              Semantics(
                  header: true,
                  child: const KoloHeadline('Content notices', size: 18)),
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
              if (widget.restrictions != null)
                MeasuresSection(repository: widget.restrictions!),
            ],
            const SizedBox(height: 16),
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
