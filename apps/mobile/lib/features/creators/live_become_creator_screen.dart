import 'package:flutter/material.dart';
import '../../core/presentation/design_node.dart';
import '../../shared/widgets/live_state_view.dart';
import 'creator_access_controller.dart';
import 'creator_shell.dart';
import 'live_creator_onboarding_repository.dart';

/// M-036 Become a creator. Shows the account's real invitation, application
/// and upload-eligibility state, and submits the invited application.
class LiveBecomeCreatorScreen extends StatefulWidget {
  const LiveBecomeCreatorScreen(
      {super.key,
      required this.catalog,
      this.onboarding,
      this.controller,
      this.screen = 36});

  final DesignCatalog catalog;
  final LiveCreatorOnboardingRepository? onboarding;

  /// Test seam for a pre-built controller.
  final CreatorAccessController? controller;
  final int screen;

  @override
  State<LiveBecomeCreatorScreen> createState() =>
      _LiveBecomeCreatorScreenState();
}

class _LiveBecomeCreatorScreenState extends State<LiveBecomeCreatorScreen> {
  late final CreatorAccessController controller;

  @override
  void initState() {
    super.initState();
    controller =
        widget.controller ?? CreatorAccessController(widget.onboarding!);
    controller.load();
  }

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Become a creator')),
        body: SafeArea(
            child: ListenableBuilder(
                listenable: controller,
                builder: (context, _) => CreatorAccessPanel(
                    controller: controller,
                    screen: widget.screen,
                    eligible: (context) => _Eligible(screen: widget.screen)))),
        bottomNavigationBar:
            creatorNavigation(context, widget.catalog, widget.screen),
      );
}

class _Eligible extends StatelessWidget {
  const _Eligible({required this.screen});
  final int screen;

  @override
  Widget build(BuildContext context) =>
      ListView(padding: const EdgeInsets.all(16), children: [
        Text('You’re a creator.',
            style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 8),
        const Text('Creator uploads are enabled for your account.'),
        const SizedBox(height: 16),
        FilledButton(
            onPressed: () => openCreatorScreen(context, 37),
            child: const Text('Open Creator Studio')),
      ]);
}

/// The onboarding content shared by M-036 and the not-yet-a-creator state of
/// Creator Studio (M-037). [eligible] builds the body once uploads are allowed.
class CreatorAccessPanel extends StatefulWidget {
  const CreatorAccessPanel(
      {super.key,
      required this.controller,
      required this.screen,
      required this.eligible});

  final CreatorAccessController controller;

  /// The screen to return to after signing in again.
  final int screen;
  final WidgetBuilder eligible;

  @override
  State<CreatorAccessPanel> createState() => _CreatorAccessPanelState();
}

class _CreatorAccessPanelState extends State<CreatorAccessPanel> {
  final handle = TextEditingController();
  bool adult = false;
  bool rights = false;
  String? handleError;

  CreatorAccessController get controller => widget.controller;

  @override
  void dispose() {
    handle.dispose();
    super.dispose();
  }

  void _submit() {
    final problem = CreatorAccessController.handleProblem(handle.text);
    setState(() => handleError = problem);
    if (problem != null) return;
    controller.submit(
        handle: handle.text, adultAttested: adult, rightsAttested: rights);
  }

  Widget _notice(BuildContext context, String title, String message) => Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Semantics(
            liveRegion: true,
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 4),
              Text(message),
            ]),
          ),
        ),
      );

  List<Widget> _status(BuildContext context) {
    final retry = OutlinedButton(
        onPressed: controller.load, child: const Text('Check again'));
    return switch (controller.phase) {
      CreatorAccessPhase.noInvitation => [
          _notice(context, 'Viewer account',
              'Uploading is available only when creator permissions are enabled for your account. Creator invitations are issued by KoloVibe, and none exists for this account yet.'),
          const SizedBox(height: 16),
          retry,
        ],
      CreatorAccessPhase.pending => [
          _notice(context, 'Application received',
              'Your creator application is awaiting review.'),
          const SizedBox(height: 16),
          retry,
        ],
      CreatorAccessPhase.rejected => [
          _notice(context, 'Application not approved',
              'Your creator application was not approved.'),
        ],
      CreatorAccessPhase.restricted => [
          _notice(context, 'Uploads restricted',
              'Creator upload is currently restricted for this account.'),
          const SizedBox(height: 16),
          retry,
        ],
      CreatorAccessPhase.invited => [
          _notice(context, 'You’re invited',
              'Choose your creator handle and confirm both statements to apply.'),
          const SizedBox(height: 16),
          TextField(
              controller: handle,
              maxLength: 30,
              enabled: !controller.submitting,
              autocorrect: false,
              textInputAction: TextInputAction.done,
              decoration: InputDecoration(
                  labelText: 'Creator handle',
                  prefixText: '@',
                  helperText: 'Lowercase letters, numbers and underscores.',
                  errorText: handleError),
              onChanged: (_) {
                if (handleError != null) setState(() => handleError = null);
              }),
          CheckboxListTile(
              value: adult,
              onChanged: controller.submitting
                  ? null
                  : (value) => setState(() => adult = value ?? false),
              title: const Text('I confirm I am an adult.')),
          CheckboxListTile(
              value: rights,
              onChanged: controller.submitting
                  ? null
                  : (value) => setState(() => rights = value ?? false),
              title: const Text('I have rights to my original content.')),
          if (controller.submitError != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Semantics(
                  liveRegion: true,
                  child: Text(controller.submitError!,
                      style: TextStyle(
                          color: Theme.of(context).colorScheme.error))),
            ),
          const SizedBox(height: 8),
          FilledButton(
              onPressed: controller.submitting ? null : _submit,
              child: Text(controller.submitting
                  ? 'Sending application…'
                  : 'Become a creator')),
        ],
      _ => const [],
    };
  }

  @override
  Widget build(BuildContext context) {
    switch (controller.phase) {
      case CreatorAccessPhase.loading:
        return const LiveStateView.loading(label: 'Checking creator access');
      case CreatorAccessPhase.failed:
        return LiveStateView.failure(controller.error!,
            onRetry: controller.load,
            onSignIn: () => signInThenReturn(context, widget.screen));
      case CreatorAccessPhase.eligible:
        return widget.eligible(context);
      default:
        return RefreshIndicator(
          onRefresh: controller.load,
          child: ListView(padding: const EdgeInsets.all(16), children: [
            Text('From viewer\nto storyteller.',
                style: Theme.of(context).textTheme.headlineMedium),
            const SizedBox(height: 8),
            const Text(
                'Ready to share your own films, music or comedy? Start with creator onboarding.'),
            const SizedBox(height: 16),
            ..._status(context),
          ]),
        );
    }
  }
}
