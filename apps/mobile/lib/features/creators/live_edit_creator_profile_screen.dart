import 'package:flutter/material.dart';
import '../../core/presentation/design_node.dart';
import '../../shared/widgets/live_state_view.dart';
import 'creator_shell.dart';
import 'live_own_creator_repository.dart';
import 'own_profile_controller.dart';

/// M-039 Edit creator profile: display name, bio, location and handle.
/// "Change profile photo" is not offered: the gateway has no photo contract.
class LiveEditCreatorProfileScreen extends StatefulWidget {
  const LiveEditCreatorProfileScreen(
      {super.key,
      required this.catalog,
      required this.profiles,
      this.controller});

  final DesignCatalog catalog;
  final LiveOwnCreatorRepository profiles;

  /// Test seam for a pre-built controller.
  final OwnProfileController? controller;

  @override
  State<LiveEditCreatorProfileScreen> createState() =>
      _LiveEditCreatorProfileScreenState();
}

class _LiveEditCreatorProfileScreenState
    extends State<LiveEditCreatorProfileScreen> {
  late final OwnProfileController controller;
  final name = TextEditingController();
  final bio = TextEditingController();
  final location = TextEditingController();
  final handle = TextEditingController();
  bool _filled = false;

  @override
  void initState() {
    super.initState();
    controller = widget.controller ?? OwnProfileController(widget.profiles);
    controller.addListener(_fill);
    controller.load();
  }

  /// Fills the form once, from the first successful read, so later reloads
  /// never overwrite what the user is typing.
  void _fill() {
    final own = controller.profile;
    if (_filled || own == null || controller.phase != OwnProfilePhase.ready) {
      return;
    }
    _filled = true;
    name.text = own.displayName;
    bio.text = own.bio;
    location.text = own.location;
    handle.text = own.handle;
  }

  @override
  void dispose() {
    controller.removeListener(_fill);
    controller.dispose();
    name.dispose();
    bio.dispose();
    location.dispose();
    handle.dispose();
    super.dispose();
  }

  bool get _changed {
    final own = controller.profile;
    return own != null &&
        (name.text.trim() != own.displayName ||
            bio.text.trim() != own.bio ||
            location.text.trim() != own.location ||
            handle.text.trim() != own.handle);
  }

  Future<void> _save() async {
    final saved = await controller.save(
        displayName: name.text,
        bio: bio.text,
        location: location.text,
        handle: handle.text);
    if (saved && mounted) Navigator.of(context).maybePop(true);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Edit creator profile')),
        body: SafeArea(
            child: ListenableBuilder(
                listenable: controller,
                builder: (context, _) => _body(context))),
        bottomNavigationBar: creatorNavigation(context, widget.catalog, 39),
      );

  Widget _body(BuildContext context) {
    switch (controller.phase) {
      case OwnProfilePhase.loading:
        return const LiveStateView.loading(label: 'Loading your profile');
      case OwnProfilePhase.failed:
        return LiveStateView.failure(controller.error!,
            onRetry: controller.load,
            onSignIn: () => signInThenReturn(context, 39));
      case OwnProfilePhase.ready:
        final busy = controller.saving;
        return ListView(padding: const EdgeInsets.all(16), children: [
          TextField(
              controller: name,
              enabled: !busy,
              maxLength: 80,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(labelText: 'Display name'),
              onChanged: (_) => setState(() {})),
          TextField(
              controller: bio,
              enabled: !busy,
              maxLength: 500,
              maxLines: 4,
              decoration: const InputDecoration(labelText: 'Bio'),
              onChanged: (_) => setState(() {})),
          TextField(
              controller: location,
              enabled: !busy,
              maxLength: 80,
              decoration: const InputDecoration(labelText: 'Location'),
              onChanged: (_) => setState(() {})),
          TextField(
              controller: handle,
              enabled: !busy,
              maxLength: 30,
              autocorrect: false,
              decoration: InputDecoration(
                  labelText: 'Creator handle',
                  prefixText: '@',
                  errorText: controller.handleError),
              onChanged: (_) => setState(() {})),
          if (controller.saveError != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Semantics(
                  liveRegion: true,
                  child: Text(controller.saveError!,
                      style: TextStyle(
                          color: Theme.of(context).colorScheme.error))),
            ),
          if (controller.error != null)
            TextButton(
                onPressed: () => signInThenReturn(context, 39),
                child: const Text('Sign in again')),
          const SizedBox(height: 8),
          FilledButton(
              onPressed: busy || !_changed ? null : _save,
              child: Text(busy ? 'Saving…' : 'Save profile')),
          TextButton(
              onPressed: busy ? null : () => Navigator.of(context).maybePop(),
              child: const Text('Cancel')),
        ]);
    }
  }
}
