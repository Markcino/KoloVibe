import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';
import '../../app/screen_route.dart';
import '../../core/platform/device_bridge.dart';
import '../account/live_account_repository.dart';
import '../../core/presentation/design_node.dart';
import '../shell/main_shell.dart';
import '../../core/network/api_client.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../engagement/live_video_engagement_repository.dart';
import '../system/system_ui.dart';
import 'live_video_repository.dart';
import 'live_video_screen.dart';

/// Only the visible page mounts a player; swiping disposes its predecessor and
/// its watch session/controller. Watch qualification remains server-owned.
class VerticalVideoFeed extends StatefulWidget {
  const VerticalVideoFeed(
      {super.key,
      required this.repository,
      this.engagement,
      required this.device,
      this.account,
      this.following = false,
      this.catalog,
      this.onNavigate,
      this.playerFactory});
  final LiveVideoRepository repository;
  final LiveVideoEngagementRepository? engagement;
  final DeviceBridge device;

  /// The Following feed (M-018) reads the signed-in account's followed
  /// creators; otherwise this is the public feed (M-024).
  final bool following;

  /// Supplies the designed bottom navigation; without it none is drawn.
  final DesignCatalog? catalog;
  final LiveAccountRepository? account;

  /// Tab and search navigation; [screen] is a design number.
  final void Function(int screen)? onNavigate;
  final VideoPlayerController Function(Uri)? playerFactory;
  @override
  State<VerticalVideoFeed> createState() => _VerticalVideoFeedState();
}

class _VerticalVideoFeedState extends State<VerticalVideoFeed> {
  final items = <LiveVideo>[];
  String? cursor;
  Object? error;
  bool busy = false;
  int active = 0;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final page = widget.following
          ? widget.account == null
              ? throw const ApiFailure(401, 'Sign in')
              : await widget.repository
                  .followingPage(widget.account!, cursor: cursor)
          : await widget.repository.page(cursor: cursor);
      if (!mounted) return;
      final seen = items.map((e) => e.id).toSet();
      if (page.items.any((e) => seen.contains(e.id))) {
        throw const FormatException('Repeated page');
      }
      items.addAll(page.items);
      cursor = page.nextCursor;
    } catch (failure) {
      error = failure;
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  void _go(int screen) {
    if (widget.onNavigate != null) {
      widget.onNavigate!(screen);
      return;
    }
    final route = ScreenRoute(screen);
    final navigator = Navigator.of(context);
    // The two feeds are sibling tabs; search and sign-in open on top.
    if (screen == 18 || screen == 24) {
      navigator.pushReplacementNamed(route.name, arguments: route);
    } else {
      navigator.pushNamed(route.name, arguments: route);
    }
  }

  Widget _tab(String label, bool selected, VoidCallback? onTap) => Semantics(
      button: true,
      selected: selected,
      child: InkWell(
          onTap: onTap,
          child: ConstrainedBox(
              constraints: const BoxConstraints(minHeight: 44, minWidth: 44),
              child: Center(
                  child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 10),
                      child: Text(label,
                          style: KoloVibeText.body(16,
                              weight:
                                  selected ? FontWeight.w700 : FontWeight.w500,
                              color: selected
                                  ? Colors.white
                                  : Colors.white60)))))));

  Widget _header() => Positioned(
      top: 0,
      left: 0,
      right: 0,
      child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
        _tab('Following', widget.following,
            widget.following ? null : () => _go(18)),
        _tab('For You', !widget.following,
            widget.following ? () => _go(24) : null),
        IconButton(
            tooltip: 'Search',
            color: Colors.white,
            onPressed: () => _go(21),
            icon: const Icon(Icons.search)),
      ]));

  Widget? _navigation() {
    final navigation = widget.catalog?[24].named('Primary navigation');
    if (navigation == null) return null;
    return MainShell(
        navigation: navigation,
        screen: widget.following ? 18 : 24,
        onSelected: (target) {
          final route = ScreenRoute(target);
          Navigator.of(context)
              .pushReplacementNamed(route.name, arguments: route);
        });
  }

  Widget _empty() => widget.following
      ? const Center(
          child: Padding(
              padding: EdgeInsets.all(24),
              child: Text('Follow creators to see their originals here.',
                  textAlign: TextAlign.center)))
      : const SystemEmpty();

  @override
  Widget build(BuildContext context) => Theme(
      data: KoloVibeTheme.dark(),
      child: Scaffold(
          backgroundColor: Colors.black,
          bottomNavigationBar: _navigation(),
          body: SafeArea(
              child: Stack(children: [
            Positioned.fill(
                child: items.isEmpty
                    ? busy
                        ? const SystemLoading()
                        : error != null
                            ? SystemFailureView(
                                error: error!,
                                onRetry: load,
                                onSignIn: () => _go(4))
                            : _empty()
                    : PageView.builder(
                        scrollDirection: Axis.vertical,
                        itemCount: items.length +
                            (cursor != null || error != null ? 1 : 0),
                        onPageChanged: (index) {
                          setState(() => active = index);
                          if (index >= items.length - 2 && cursor != null) {
                            load();
                          }
                        },
                        itemBuilder: (context, index) {
                          if (index == items.length) {
                            return error != null
                                ? SystemFailureView(
                                    error: error!,
                                    onRetry: load,
                                    onSignIn: () => _go(4))
                                : const SystemLoading();
                          }
                          if (index != active) {
                            return Center(child: Text(items[index].title));
                          }
                          return LiveVideoDetailScreen(
                              key: ValueKey(items[index].id),
                              id: items[index].id,
                              repository: widget.repository,
                              engagement: widget.engagement,
                              fullScreen: true,
                              playerFactory: widget.playerFactory,
                              device: widget.device);
                        })),
            _header(),
          ]))));
}
