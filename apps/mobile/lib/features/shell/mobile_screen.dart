import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../app/app_dependencies.dart';
import '../../app/app_session.dart';
import '../../app/screen_route.dart';
import '../../core/presentation/design_node.dart';
import '../../core/presentation/feature_repository.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/design_view.dart';
import 'main_shell.dart';
import 'screen_controller.dart';

class MobileScreen extends StatefulWidget {
  const MobileScreen({
    super.key,
    required this.route,
    required this.catalog,
    required this.dependencies,
    required this.session,
  });
  final ScreenRoute route;
  final DesignCatalog catalog;
  final AppDependencies dependencies;
  final AppSession session;
  @override
  State<MobileScreen> createState() => _MobileScreenState();
}

class _MobileScreenState extends State<MobileScreen> {
  late final ScreenController controller;
  final form = GlobalKey<FormState>();
  Timer? timer;
  bool discardConfirmed = false;
  int get id => widget.route.screen;
  DesignScreen get screen => widget.catalog[id];
  bool get protected => !(id <= 12 ||
      {
        15,
        87,
        88,
        89,
        95,
        96,
        97,
        98,
        99,
        101,
        102,
        103,
        108,
      }.contains(id));
  @override
  void initState() {
    super.initState();
    controller = ScreenController(widget.dependencies.repository);
    if (id == 72 || id == 74) {
      controller.reason =
          widget.session.reportReason ?? 'Rights or ownership concern';
    }
    if (id == 101) widget.session.expire();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (id == 1) {
        timer = Timer(const Duration(milliseconds: 900), () {
          if (mounted) navigate(2, replace: true);
        });
      }
    });
  }

  @override
  void dispose() {
    timer?.cancel();
    controller.dispose();
    super.dispose();
  }

  Future<void> navigate(
    int target, {
    bool replace = false,
    bool reset = false,
  }) async {
    if (target == 101) widget.session.expire(destination: id);
    final next = ScreenRoute(
      target,
      entityId: widget.route.entityId,
      returnTo: target == 4 ? widget.session.returnTo : null,
    );
    if (reset) {
      Navigator.of(
        context,
      ).pushNamedAndRemoveUntil(next.name, (_) => false, arguments: next);
    } else if (replace) {
      Navigator.of(context).pushReplacementNamed(next.name, arguments: next);
    } else {
      Navigator.of(context).pushNamed(next.name, arguments: next);
    }
  }

  void notify(String message) => ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(message)));

  Future<void> action(String action) async {
    if (controller.busy) return;
    if (action == 'back') {
      await back();
      return;
    }
    if (action.startsWith('reason:')) {
      controller.choose(action.substring(7), report: true);
      return;
    }
    if (action.startsWith('select:')) {
      controller.choose(action.substring(7));
      return;
    }
    if (action == 'category') {
      await category();
      return;
    }
    if (action == 'search') {
      final q = (controller.fields['query'] ?? '').trim().toLowerCase();
      await navigate(q.isEmpty || q.contains('orchestra') ? 98 : 22);
      return;
    }
    if (action.startsWith('go:')) {
      final target = int.parse(action.substring(3));
      if (id == 71 && target == 72 && controller.reason.isEmpty) {
        notify('Choose a reason before continuing.');
        return;
      }
      if (id == 71 && target == 72) {
        widget.session.reportReason = controller.reason;
      }
      if (id == 44 &&
          target == 45 &&
          !(form.currentState?.validate() ?? false)) {
        return;
      }
      final next = target == 7 && widget.dependencies.liveAccount != null
          ? 8
          : target;
      await navigate(next);
      return;
    }
    if (action == 'unavailable') {
      notify(
        'This capability requires its connected service. No action was taken.',
      );
      return;
    }
    if (!action.startsWith('do:')) return;
    final operation = UiOperation.values.firstWhere(
      (op) => op.name == action.substring(3),
    );
    final validates = {
      UiOperation.signIn,
      UiOperation.register,
      UiOperation.resetPassword,
      UiOperation.reauthenticate,
      UiOperation.saveProfile,
      UiOperation.deleteAccount,
      UiOperation.requestReset,
      UiOperation.requestCode,
      UiOperation.verifyEmail,
      UiOperation.deleteVideo,
    }.contains(operation);
    if (validates && !(form.currentState?.validate() ?? true)) {
      return;
    }
    if ({UiOperation.register, UiOperation.deleteAccount}.contains(operation) &&
        !controller.acknowledged) {
      notify('Please acknowledge the information before continuing.');
      return;
    }
    FocusScope.of(context).unfocus();
    final result = await controller.submit(operation);
    if (!mounted || result == null) return;
    if (!result.available) {
      notify(result.message);
      return;
    }
    if (widget.dependencies.liveAccount != null) {
      switch (operation) {
        case UiOperation.register:
          await navigate(6);
          return;
        case UiOperation.requestCode:
          notify(result.message);
          await navigate(6);
          return;
        case UiOperation.verifyEmail:
          await navigate(4, reset: true);
          return;
        case UiOperation.signIn:
          await navigate(79, reset: true);
          return;
        case UiOperation.signOut:
          await navigate(2, reset: true);
          return;
        default:
          break;
      }
    }
  }

  Future<void> category() async {
    final value = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            for (final category in const [
              'Hipco',
              'Afrobeats',
              'Comedy',
              'Skits',
              'Short films',
              'Culture',
              'Documentaries',
            ])
              ListTile(
                title: Text(category),
                onTap: () => Navigator.pop(context, category),
              ),
          ],
        ),
      ),
    );
    if (value != null && mounted) {
      controller.update('Category · Required', value);
      notify('Category: $value');
    }
  }

  Future<bool> confirmLeave() async {
    if (!controller.dirty || discardConfirmed) return true;
    return await showModalBottomSheet<bool>(
          context: context,
          showDragHandle: true,
          builder: (context) => SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'Keep your changes?',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 16),
                  const Text(
                    'Leaving discards changes that have not been submitted.',
                  ),
                  const SizedBox(height: 20),
                  FilledButton(
                    onPressed: () => Navigator.pop(context, false),
                    child: const Text('Keep editing'),
                  ),
                  TextButton(
                    onPressed: () => Navigator.pop(context, true),
                    child: const Text('Discard changes'),
                  ),
                ],
              ),
            ),
          ),
        ) ??
        false;
  }

  Future<void> back() async {
    if (!await confirmLeave() || !mounted) return;
    discardConfirmed = true;
    if (Navigator.of(context).canPop()) {
      Navigator.of(context).pop();
    } else {
      await navigate(2, replace: true);
    }
  }

  Widget view(DesignNode node) => DesignView(
        node: node,
        controller: controller,
        onAction: action,
      );

  Widget body() {
    if (protected) {
      return unavailable();
    }
    if (id == 1) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (screen.named('KoloVibe wordmark') != null)
              view(screen.named('KoloVibe wordmark')!),
            const SizedBox(height: 24),
            const Text(
              'Our stories. Our rhythm. Our vibe.',
              style: TextStyle(color: Colors.white),
            ),
            const SizedBox(height: 48),
            const CircularProgressIndicator(),
            const SizedBox(height: 16),
            const Text(
              'Finding your vibe…',
              style: TextStyle(color: Colors.white70),
            ),
          ],
        ),
      );
    }
    if (id == 2) return welcome();
    if (screen.named('Film footage') != null) return player();
    final content = screen.named('Scrollable content'),
        header = screen.named('App header');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (header != null) view(header),
        Expanded(
          child: SingleChildScrollView(
            key: PageStorageKey('M-$id'),
            child: content == null ? const SizedBox.shrink() : view(content),
          ),
        ),
      ],
    );
  }

  Widget welcome() {
    final image = screen.named('Welcome photograph'),
        brand = screen.named('Brand'),
        message = screen.named('Welcome message');
    return LayoutBuilder(
      builder: (context, constraints) => SingleChildScrollView(
        child: ConstrainedBox(
          constraints: BoxConstraints(minHeight: constraints.maxHeight),
          child: Stack(
            children: [
              if (image != null)
                SizedBox(
                  height: 540,
                  width: double.infinity,
                  child: view(image),
                ),
              Positioned(
                top: 230,
                left: 0,
                right: 0,
                height: 340,
                child: Container(
                  decoration: const BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [Colors.transparent, KoloVibeColors.deepNavy],
                    ),
                  ),
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (brand != null)
                    Padding(
                      padding: const EdgeInsets.fromLTRB(24, 20, 24, 0),
                      child: view(brand),
                    ),
                  const SizedBox(height: 330),
                  if (message != null)
                    Padding(
                      padding: const EdgeInsets.fromLTRB(24, 0, 24, 40),
                      child: view(message),
                    ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget player() => LayoutBuilder(
      builder: (context, constraints) => Stack(fit: StackFit.expand, children: [
            view(screen.named('Film footage')!),
            const DecoratedBox(
                decoration: BoxDecoration(
                    gradient: LinearGradient(
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                        colors: [
                  Color(0x33001539),
                  Color(0x11001539),
                  Color(0xee001539)
                ]))),
            Align(
                alignment: Alignment.topCenter,
                child: SizedBox(
                    height: 52,
                    child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Text('Following',
                              style: TextStyle(
                                  color: Color(0xff8fa6be),
                                  fontSize: 16,
                                  fontWeight: FontWeight.w500)),
                          SizedBox(
                              width: MediaQuery.textScalerOf(context).scale(1) >
                                      1.3
                                  ? 8
                                  : 24),
                          const Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text('For You',
                                    style: TextStyle(
                                        color: Colors.white,
                                        fontSize: 16,
                                        fontWeight: FontWeight.w800)),
                                SizedBox(height: 8),
                                SizedBox(
                                    width: 40,
                                    height: 3,
                                    child:
                                        ColoredBox(color: KoloVibeColors.red)),
                              ]),
                          SizedBox(
                              width: MediaQuery.textScalerOf(context).scale(1) >
                                      1.3
                                  ? 8
                                  : 20),
                          IconButton(
                              tooltip: 'Search videos',
                              onPressed: () => navigate(21),
                              constraints: const BoxConstraints.tightFor(
                                  width: 36, height: 36),
                              padding: EdgeInsets.zero,
                              icon: const Icon(Icons.search,
                                  color: Colors.white)),
                        ]))),
            Positioned(
                left: 0,
                right: 0,
                bottom: 70,
                child: ConstrainedBox(
                    constraints:
                        BoxConstraints(maxHeight: constraints.maxHeight * .65),
                    child: SingleChildScrollView(
                        child: Row(
                            crossAxisAlignment: CrossAxisAlignment.end,
                            children: [
                          Expanded(
                              child: Padding(
                                  padding: const EdgeInsets.all(20),
                                  child: view(screen.named('Video caption')!))),
                          Padding(
                              padding:
                                  const EdgeInsets.only(right: 16, bottom: 16),
                              child: SizedBox(
                                  width: 48,
                                  child:
                                      view(screen.named('Engagement rail')!))),
                        ])))),
            Positioned(
                left: 20,
                right: 20,
                bottom: 8,
                child: Column(mainAxisSize: MainAxisSize.min, children: [
                  if (screen.named('Playback controls') != null)
                    view(screen.named('Playback controls')!),
                  const SizedBox(height: 8),
                  const Text('Preview only · Video playback is not connected',
                      style: TextStyle(fontSize: 11, color: Colors.white)),
                ])),
            if (id == 32)
              const Center(
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                CircularProgressIndicator(color: Colors.white),
                SizedBox(height: 12),
                Text('Preparing playback…',
                    style: TextStyle(color: Colors.white))
              ])),
            if (id == 33)
              Center(
                  child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: ConstrainedBox(
                          constraints: BoxConstraints(
                              maxHeight: constraints.maxHeight * .6),
                          child: SingleChildScrollView(
                              child: view(screen.named('Playback error')!))))),
          ]));
  Widget unavailable() => Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.cloud_off_outlined,
                size: 48,
                color: screen.isDark
                    ? KoloVibeColors.softBlue
                    : KoloVibeColors.navy,
              ),
              const SizedBox(height: 20),
              Text(
                'This service is not connected yet.',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      color: screen.isDark ? Colors.white : null,
                    ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 12),
              Text(
                'Account access, content and actions become available when their secure services are connected.',
                style: screen.isDark
                    ? const TextStyle(color: KoloVibeColors.softBlue)
                    : null,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 24),
              FilledButton(
                onPressed: () => navigate(2),
                style: screen.isDark
                    ? FilledButton.styleFrom(
                        backgroundColor: KoloVibeColors.softBlue,
                        foregroundColor: KoloVibeColors.navy,
                      )
                    : null,
                child: const Text('Return to welcome'),
              ),
            ],
          ),
        ),
      );
  @override
  Widget build(BuildContext context) => AnimatedBuilder(
        animation: controller,
        builder: (context, _) => PopScope(
          canPop: !controller.dirty || discardConfirmed,
          onPopInvokedWithResult: (didPop, _) async {
            if (!didPop && await confirmLeave() && mounted) {
              setState(() => discardConfirmed = true);
              WidgetsBinding.instance.addPostFrameCallback((_) {
                if (mounted) Navigator.pop(context);
              });
            }
          },
          child: AnnotatedRegion<SystemUiOverlayStyle>(
            value: screen.isDark
                ? SystemUiOverlayStyle.light
                : SystemUiOverlayStyle.dark,
            child: Scaffold(
              backgroundColor: Color(
                screen.root.style['background'] as int? ?? 0xfff0f3ff,
              ),
              body: SafeArea(
                bottom: !screen.hasNavigation,
                child: Form(
                  key: form,
                  child: Column(
                    children: [
                      Expanded(child: body()),
                      if (controller.error != null)
                        Padding(
                          padding: const EdgeInsets.all(16),
                          child: Semantics(
                            liveRegion: true,
                            child: Text(
                              controller.error!,
                              style: const TextStyle(color: KoloVibeColors.red),
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
              bottomNavigationBar: screen.hasNavigation
                  ? MainShell(
                      navigation: screen.named('Primary navigation')!,
                      screen: id,
                      onSelected: (target) => navigate(target, replace: true),
                    )
                  : null,
            ),
          ),
        ),
      );
}
