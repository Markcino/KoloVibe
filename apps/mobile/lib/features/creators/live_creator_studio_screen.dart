import 'package:flutter/material.dart';
import '../../core/presentation/design_node.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/live_state_view.dart';
import 'creator_access_controller.dart';
import 'creator_shell.dart';
import 'live_become_creator_screen.dart';
import 'live_analytics_repository.dart';
import 'live_analytics_screen.dart';
import 'live_creator_onboarding_repository.dart';
import 'live_own_creator_repository.dart';
import 'own_profile_controller.dart';

/// M-037 Creator Studio. Approved creators see their real profile name and the
/// studio actions; other accounts see the onboarding state instead (M-036).
/// Analytics tiles belong to the analytics journey (M-058) and are not shown
/// here until that journey reads the analytics API.
class LiveCreatorStudioScreen extends StatefulWidget {
  const LiveCreatorStudioScreen(
      {super.key,
      required this.catalog,
      required this.onboarding,
      required this.profiles,
      this.access,
      this.analytics,
      this.profile});

  final DesignCatalog catalog;
  final LiveCreatorOnboardingRepository onboarding;
  final LiveOwnCreatorRepository profiles;

  /// Reads the last seven days for the studio summary card (optional).
  final LiveAnalyticsRepository? analytics;

  /// Test seams for pre-built controllers.
  final CreatorAccessController? access;
  final OwnProfileController? profile;

  @override
  State<LiveCreatorStudioScreen> createState() =>
      _LiveCreatorStudioScreenState();
}

class _LiveCreatorStudioScreenState extends State<LiveCreatorStudioScreen> {
  late final CreatorAccessController access;
  late final OwnProfileController profile;
  bool _profileRequested = false;
  CreatorAnalytics? _summary;

  @override
  void initState() {
    super.initState();
    access = widget.access ?? CreatorAccessController(widget.onboarding);
    profile = widget.profile ?? OwnProfileController(widget.profiles);
    access.addListener(_accessChanged);
    access.load();
  }

  void _accessChanged() {
    if (access.phase == CreatorAccessPhase.eligible && !_profileRequested) {
      _profileRequested = true;
      profile.load();
      _loadSummary();
    }
    if (access.phase != CreatorAccessPhase.eligible) _profileRequested = false;
  }

  /// The summary card is optional: when analytics are closed, empty or fail,
  /// the studio shows the Analytics entry instead of the card.
  Future<void> _loadSummary() async {
    final repository = widget.analytics;
    if (repository == null) return;
    try {
      final value = await repository.creator('7d');
      if (mounted) setState(() => _summary = value);
    } catch (_) {
      if (mounted) setState(() => _summary = null);
    }
  }

  @override
  void dispose() {
    access.removeListener(_accessChanged);
    access.dispose();
    profile.dispose();
    super.dispose();
  }

  @override
  // The approved Creator Studio design is drawn on the deep navy surface.
  Widget build(BuildContext context) => Theme(
        data: KoloVibeTheme.dark(),
        child: Scaffold(
          appBar: AppBar(title: const Text('Creator Studio')),
          body: SafeArea(
              child: ListenableBuilder(
                  listenable: Listenable.merge([access, profile]),
                  builder: (context, _) => CreatorAccessPanel(
                      controller: access, screen: 37, eligible: _studio))),
          bottomNavigationBar: creatorNavigation(context, widget.catalog, 37),
        ),
      );

  Widget _studio(BuildContext context) {
    if (profile.phase == OwnProfilePhase.loading) {
      return const LiveStateView.loading(label: 'Loading Creator Studio');
    }
    if (profile.phase == OwnProfilePhase.failed) {
      return LiveStateView.failure(profile.error!,
          onRetry: profile.load, onSignIn: () => signInThenReturn(context, 37));
    }
    final own = profile.profile!;
    return RefreshIndicator(
      onRefresh: profile.load,
      child: ListView(
          padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
          children: [
            Text('Good stories travel.',
                style: Theme.of(context).textTheme.headlineMedium),
            const SizedBox(height: 4),
            Text('${own.title} · Creator enabled',
                style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 20),
            if (_summary != null && !_summary!.empty) ...[
              _summaryCard(context, _summary!),
              const SizedBox(height: 16),
            ],
            FilledButton.icon(
                onPressed: () => openCreatorScreen(context, 41),
                icon: const Icon(Icons.add),
                label: const Text('Publish an original')),
            const SizedBox(height: 16),
            _tile(
                context, 'Analytics', 'Qualified activity and watch time', 58),
            _tile(context, 'My video library', 'Your drafts and originals', 40),
            _tile(context, 'Creator profile', '@${own.handle}', 38),
            _tile(context, 'Lone Stars', 'Non-cash recognition points', 61),
          ]),
    );
  }

  Widget _summaryCard(BuildContext context, CreatorAnalytics data) => InkWell(
        borderRadius: BorderRadius.circular(KoloVibeRadii.card),
        onTap: () => openCreatorScreen(context, 58),
        child: Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(KoloVibeRadii.card)),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              for (final (label, value) in [
                ('Qualified plays', analyticsCount(data.qualifiedPlays)),
                ('Watch time', watchTime(data.watchTimeSeconds)),
              ])
                Expanded(
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                      Text(label, style: KoloVibeText.body(11)),
                      const SizedBox(height: 5),
                      Text(value, style: KoloVibeText.heading(26)),
                    ])),
            ]),
            const SizedBox(height: 12),
            AnalyticsChart(days: data.daily),
            const SizedBox(height: 8),
            Text('Last 7 days · View full analytics',
                style: KoloVibeText.body(10)),
          ]),
        ),
      );

  Widget _tile(
          BuildContext context, String title, String subtitle, int screen) =>
      ListTile(
          title: Text(title),
          subtitle: Text(subtitle),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => openCreatorScreen(context, screen));
}
