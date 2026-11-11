import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';
import '../../core/platform/device_bridge.dart';
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
      this.playerFactory});
  final LiveVideoRepository repository;
  final LiveVideoEngagementRepository? engagement;
  final DeviceBridge device;
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
      final page = await widget.repository.page(cursor: cursor);
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

  @override
  Widget build(BuildContext context) => Scaffold(
      body: SafeArea(
          child: items.isEmpty
              ? busy
                  ? const SystemLoading()
                  : error != null
                      ? SystemFailureView(error: error!, onRetry: load)
                      : const SystemEmpty()
              : PageView.builder(
                  scrollDirection: Axis.vertical,
                  itemCount:
                      items.length + (cursor != null || error != null ? 1 : 0),
                  onPageChanged: (index) {
                    setState(() => active = index);
                    if (index >= items.length - 2 && cursor != null) load();
                  },
                  itemBuilder: (context, index) {
                    if (index == items.length) {
                      return error != null
                          ? SystemFailureView(error: error!, onRetry: load)
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
                  })));
}
