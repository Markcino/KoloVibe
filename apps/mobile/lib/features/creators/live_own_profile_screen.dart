import 'package:flutter/material.dart';
import '../../app/screen_route.dart';
import '../../core/presentation/design_node.dart';
import '../../shared/widgets/live_state_view.dart';
import 'creator_shell.dart';
import 'live_creator_repository.dart';
import 'live_own_creator_repository.dart';
import 'own_profile_controller.dart';

/// M-038 Creator profile: the creator's real public fields, with links to the
/// public preview (M-026), published originals (M-027) and editing (M-039).
/// There is no profile-photo API, so no photo is shown or offered.
class LiveOwnProfileScreen extends StatefulWidget {
  const LiveOwnProfileScreen(
      {super.key,
      required this.catalog,
      required this.profiles,
      this.publicCreators,
      this.controller});

  final DesignCatalog catalog;
  final LiveOwnCreatorRepository profiles;

  /// Supplies the published-video count; optional and failure-tolerant.
  final LiveCreatorRepository? publicCreators;

  /// Test seam for a pre-built controller.
  final OwnProfileController? controller;

  @override
  State<LiveOwnProfileScreen> createState() => _LiveOwnProfileScreenState();
}

class _LiveOwnProfileScreenState extends State<LiveOwnProfileScreen> {
  late final OwnProfileController controller;

  @override
  void initState() {
    super.initState();
    controller = widget.controller ??
        OwnProfileController(widget.profiles,
            publicCreators: widget.publicCreators);
    controller.load();
  }

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  Future<void> _edit() async {
    const route = ScreenRoute(39);
    // The app builds `MaterialPageRoute<void>`, so ask for Object? (not bool).
    final saved = await Navigator.of(context)
        .pushNamed<Object?>(route.name, arguments: route);
    if (saved == true && mounted) await controller.load();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Creator profile')),
        body: SafeArea(
            child: ListenableBuilder(
                listenable: controller,
                builder: (context, _) => _body(context))),
        bottomNavigationBar: creatorNavigation(context, widget.catalog, 38),
      );

  Widget _body(BuildContext context) {
    switch (controller.phase) {
      case OwnProfilePhase.loading:
        return const LiveStateView.loading(label: 'Loading your profile');
      case OwnProfilePhase.failed:
        return LiveStateView.failure(controller.error!,
            onRetry: controller.load,
            onSignIn: () => signInThenReturn(context, 38));
      case OwnProfilePhase.ready:
        final own = controller.profile!;
        final count = controller.publishedVideoCount;
        final facts = [
          '@${own.handle}',
          if (own.location.isNotEmpty) own.location,
        ].join(' · ');
        return RefreshIndicator(
          onRefresh: controller.load,
          child: ListView(padding: const EdgeInsets.all(16), children: [
            Text(own.title, style: Theme.of(context).textTheme.headlineSmall),
            Text(facts),
            const SizedBox(height: 16),
            Text('Your public introduction.',
                style: Theme.of(context).textTheme.headlineMedium),
            const SizedBox(height: 8),
            Card(
                child: Padding(
              padding: const EdgeInsets.all(16),
              child: Text(
                  own.bio.isEmpty ? 'You haven’t written a bio yet.' : own.bio),
            )),
            ListTile(
                title: const Text('Public profile preview'),
                subtitle: const Text('See what viewers see'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => openCreatorScreen(context, 26, entityId: own.id)),
            ListTile(
                title: const Text('Published originals'),
                subtitle: count == null
                    ? null
                    : Text(count == 1 ? '1 video' : '$count videos'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => openCreatorScreen(context, 27, entityId: own.id)),
            const SizedBox(height: 8),
            FilledButton(
                onPressed: _edit, child: const Text('Edit creator profile')),
            const SizedBox(height: 16),
            const Card(
                child: ListTile(
              title: Text('Your creator identity'),
              subtitle:
                  Text('Only approved public fields can be updated here.'),
            )),
          ]),
        );
    }
  }
}
