import 'package:flutter/material.dart';
import '../../core/presentation/design_node.dart';
import '../../shared/widgets/live_state_view.dart';
import 'creator_access_controller.dart';
import 'creator_shell.dart';
import 'live_become_creator_screen.dart';
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
      this.profile});

  final DesignCatalog catalog;
  final LiveCreatorOnboardingRepository onboarding;
  final LiveOwnCreatorRepository profiles;

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
    }
    if (access.phase != CreatorAccessPhase.eligible) _profileRequested = false;
  }

  @override
  void dispose() {
    access.removeListener(_accessChanged);
    access.dispose();
    profile.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Creator Studio')),
        body: SafeArea(
            child: ListenableBuilder(
                listenable: Listenable.merge([access, profile]),
                builder: (context, _) => CreatorAccessPanel(
                    controller: access, screen: 37, eligible: _studio))),
        bottomNavigationBar: creatorNavigation(context, widget.catalog, 37),
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
      child: ListView(padding: const EdgeInsets.all(16), children: [
        Text('Good stories travel.',
            style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: 4),
        Text('${own.title} · Creator enabled'),
        const SizedBox(height: 16),
        FilledButton.icon(
            onPressed: () => openCreatorScreen(context, 41),
            icon: const Icon(Icons.add),
            label: const Text('Publish an original')),
        const SizedBox(height: 8),
        _tile(context, 'My video library', 'Your drafts and originals', 40),
        _tile(context, 'Creator profile', '@${own.handle}', 38),
      ]),
    );
  }

  Widget _tile(
          BuildContext context, String title, String subtitle, int screen) =>
      ListTile(
          title: Text(title),
          subtitle: Text(subtitle),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => openCreatorScreen(context, screen));
}
