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
  final overlayForm = GlobalKey<FormState>();
  Timer? timer;
  bool overlayOpen = false, discardConfirmed = false;
  bool get demo => widget.dependencies.demo;
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
  bool get creatorOnly => id >= 37 && id <= 69;
  @override
  void initState() {
    super.initState();
    controller = ScreenController(widget.dependencies.repository);
    if (id == 72 || id == 74)
      controller.reason =
          widget.session.reportReason ?? 'Rights or ownership concern';
    if (id == 101) widget.session.expire();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final next = id == 1
          ? 2
          : demo && id == 46
              ? 49
              : demo && id == 49
                  ? 50
                  : null;
      if (next != null) {
        timer = Timer(Duration(milliseconds: id == 1 ? 900 : 3000), () {
          if (mounted) navigate(next, replace: true);
        });
      }
      if (demo) showDesignedOverlay();
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
    if (overlayOpen) {
      Navigator.of(context).pop();
      overlayOpen = false;
    }
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
      if (id == 71 && target == 72)
        widget.session.reportReason = controller.reason;
      if (id == 44 &&
          target == 45 &&
          !(form.currentState?.validate() ?? false)) {
        return;
      }
      await navigate(target);
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
      UiOperation.verifyEmail,
      UiOperation.deleteVideo,
    }.contains(operation);
    if (validates &&
        !((overlayOpen ? overlayForm.currentState : form.currentState)
                ?.validate() ??
            true)) return;
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
    if (!demo) return;
    switch (operation) {
      case UiOperation.signIn:
        final target = widget.session.returnTo ?? 17;
        widget.session.returnTo = null;
        await navigate(target, reset: true);
      case UiOperation.register:
        await navigate(6, replace: true);
      case UiOperation.verifyEmail:
        await navigate(13, replace: true);
      case UiOperation.requestCode:
        await navigate(6, replace: true);
      case UiOperation.resetPassword:
        await navigate(id == 82 ? 85 : 11, replace: true);
      case UiOperation.reauthenticate:
        await navigate(92, replace: true);
      case UiOperation.selectMedia:
        await navigate(44);
      case UiOperation.upload:
        await navigate(46, replace: true);
      case UiOperation.saveProfile:
        await navigate(
          id == 54
              ? 53
              : id == 80
                  ? 79
                  : 107,
          replace: true,
        );
      case UiOperation.unpublish:
        await navigate(40, replace: true);
        notify(result.message);
      case UiOperation.deleteVideo:
        await navigate(40, replace: true);
        notify(result.message);
      case UiOperation.report:
        await navigate(73, replace: true);
      case UiOperation.privacyRequest:
        await navigate(94);
      case UiOperation.deleteAccount:
        widget.session.clear();
        await navigate(93, reset: true);
      case UiOperation.signOut:
        widget.session.clear();
        await navigate(2, reset: true);
      case UiOperation.follow:
        widget.session.following = !widget.session.following;
        notify(
          widget.session.following
              ? 'Demo: following Ama Kollie'
              : 'Demo: unfollowed Ama Kollie',
        );
        if (widget.session.following) await navigate(28);
      case UiOperation.like:
        widget.session.liked = !widget.session.liked;
        await navigate(widget.session.liked ? 29 : 24, replace: true);
      default:
        notify(result.message);
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

  Future<void> showDesignedOverlay() async {
    final sheet = screen.named('Bottom sheet'),
        dialog = screen.named('Confirmation dialog');
    if (sheet == null && dialog == null) return;
    overlayOpen = true;
    if (sheet != null) {
      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        barrierColor: const Color(0xc9001539),
        backgroundColor: KoloVibeColors.lavender,
        builder: (context) => SafeArea(
            child: Form(
                key: overlayForm,
                child: SingleChildScrollView(child: view(sheet)))),
      );
    } else {
      await showDialog<void>(
        context: context,
        barrierColor: const Color(0xc9001539),
        builder: (context) => Dialog(
            child: Form(
                key: overlayForm,
                child: SingleChildScrollView(child: view(dialog!)))),
      );
    }
    if (mounted) overlayOpen = false;
  }

  Widget view(DesignNode node) => DesignView(
        node: node,
        controller: controller,
        onAction: action,
        demo: demo,
      );

  Widget body() {
    if ((!demo && protected) ||
        (demo && creatorOnly && widget.session.viewerPreview)) {
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
                child: view(screen.named('Feed switcher')!)),
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
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.cloud_off_outlined,
                size: 48,
                color: KoloVibeColors.navy,
              ),
              const SizedBox(height: 20),
              Text(
                demo
                    ? 'Creator access required'
                    : 'This service is not connected yet.',
                style: Theme.of(context).textTheme.titleLarge,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 12),
              Text(
                demo
                    ? 'A viewer cannot publish or manage creator content.'
                    : 'Account access, content and actions become available when their secure services are connected.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 24),
              FilledButton(
                onPressed: () => navigate(demo ? 36 : 2),
                child: Text(
                  demo ? 'Explore creator onboarding' : 'Return to welcome',
                ),
              ),
            ],
          ),
        ),
      );
  Future<void> gallery() async {
    final selected = await showModalBottomSheet<int>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: SizedBox(
          height: MediaQuery.sizeOf(context).height * .8,
          child: Column(
            children: [
              const Text(
                'Design preview · 108 screens and states',
                style: TextStyle(fontWeight: FontWeight.w700),
              ),
              SwitchListTile(
                title: const Text('Preview as viewer (restrict creator tools)'),
                value: widget.session.viewerPreview,
                onChanged: (v) {
                  widget.session.viewerPreview = v;
                  Navigator.pop(context);
                  if (mounted) setState(() {});
                },
              ),
              Expanded(
                child: ListView.builder(
                  itemCount: 108,
                  itemBuilder: (context, index) {
                    final d = widget.catalog[index + 1];
                    return ListTile(
                      title: Text(
                        'M-${d.number.toString().padLeft(3, '0')} · ${d.name}',
                      ),
                      onTap: () => Navigator.pop(context, d.number),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
    if (selected != null && mounted) await navigate(selected);
  }

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
                      if (demo)
                        Material(
                          color: KoloVibeColors.gold,
                          child: InkWell(
                            onTap: gallery,
                            child: const Padding(
                              padding: EdgeInsets.symmetric(
                                horizontal: 16,
                                vertical: 6,
                              ),
                              child: Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(Icons.science_outlined, size: 16),
                                  SizedBox(width: 8),
                                  Flexible(
                                    child: Text(
                                      'DEMO · Sample data · Browse 108 states',
                                      style: TextStyle(
                                        fontSize: 11,
                                        fontWeight: FontWeight.w700,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
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
