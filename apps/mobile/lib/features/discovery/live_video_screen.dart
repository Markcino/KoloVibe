import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';
import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import '../../core/presentation/design_node.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../shell/main_shell.dart';
import '../creators/live_creator_repository.dart';
import '../creators/creator_search_screen.dart';
import '../account/live_account_repository.dart';
import '../engagement/live_video_engagement_controller.dart';
import '../engagement/live_video_engagement_repository.dart';
import 'live_video_repository.dart';

class LiveVideoScreen extends StatefulWidget {
  const LiveVideoScreen(
      {super.key,
      required this.route,
      required this.catalog,
      required this.repository,
      this.creators,
      this.account});
  final ScreenRoute route;
  final DesignCatalog catalog;
  final LiveVideoRepository repository;
  final LiveCreatorRepository? creators;
  final LiveAccountRepository? account;

  @override
  State<LiveVideoScreen> createState() => _LiveVideoScreenState();
}

class _LiveVideoScreenState extends State<LiveVideoScreen> {
  List<LiveVideo>? videos;
  String? nextCursor;
  String? error;
  bool loading = false;
  String? query;

  @override
  void initState() {
    super.initState();
    load(reset: true);
  }

  Future<void> load({bool reset = false}) async {
    if (loading) return;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final page = widget.route.screen == 18 && widget.account != null
          ? await widget.repository
              .followingPage(widget.account!, cursor: reset ? null : nextCursor)
          : await widget.repository
              .page(cursor: reset ? null : nextCursor, query: query);
      final existing = reset ? <LiveVideo>[] : videos ?? <LiveVideo>[];
      final ids = existing.map((video) => video.id).toSet();
      if (page.items.any((video) => ids.contains(video.id))) {
        throw const FormatException('Repeated video page');
      }
      if (!mounted) return;
      setState(() {
        videos = [...existing, ...page.items];
        nextCursor = page.nextCursor;
      });
    } on ApiFailure catch (failure) {
      if (mounted) setState(() => error = failure.message);
    } on FormatException {
      if (mounted) {
        setState(() => error = 'The service returned an invalid video page.');
      }
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  void navigate(int screen, {String? entityId}) {
    final route = ScreenRoute(screen, entityId: entityId);
    Navigator.of(context).pushReplacementNamed(route.name, arguments: route);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
            actions: [
              if (widget.route.screen == 17 && widget.account != null)
                TextButton(
                  onPressed: () {
                    const route = ScreenRoute(18);
                    Navigator.of(context)
                        .pushNamed(route.name, arguments: route);
                  },
                  child: const Text('Following'),
                ),
              if (widget.route.screen == 19 && widget.creators != null)
                TextButton(
                  onPressed: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                        builder: (_) =>
                            CreatorSearchScreen(repository: widget.creators!)),
                  ),
                  child: const Text('Find creators'),
                ),
            ],
            title: Text(widget.route.screen == 17
                ? 'KoloVibe'
                : widget.route.screen == 18
                    ? 'Following'
                    : widget.route.screen == 24
                        ? 'Videos'
                        : 'Explore')),
        body: SafeArea(
            child: Column(children: [
          if (widget.route.screen == 19)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: TextField(
                enabled: !loading,
                maxLength: 100,
                textInputAction: TextInputAction.search,
                decoration: const InputDecoration(labelText: 'Search videos'),
                onSubmitted: (value) {
                  if (loading) return;
                  final term = value.trim();
                  setState(() {
                    query = term.isEmpty ? null : term;
                    videos = null;
                    nextCursor = null;
                  });
                  load(reset: true);
                },
              ),
            ),
          Expanded(child: Builder(
            builder: (context) {
              if (videos == null && loading) {
                return const Center(child: CircularProgressIndicator());
              }
              if (videos == null) {
                return _state(
                    context, error ?? 'Videos are temporarily unavailable.',
                    onRetry: () => load(reset: true));
              }
              final items = videos!;
              if (items.isEmpty) {
                return _state(
                    context,
                    error ??
                        (widget.route.screen == 18
                            ? 'Follow creators to see their originals here.'
                            : query == null
                                ? 'No originals are available yet.'
                                : 'No videos match your search.'),
                    onRetry: () => load(reset: true));
              }
              return RefreshIndicator(
                onRefresh: () => load(reset: true),
                child: ListView.separated(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.all(16),
                  itemCount: items.length + 1,
                  separatorBuilder: (_, __) => const SizedBox(height: 12),
                  itemBuilder: (context, index) {
                    if (index == items.length) {
                      return Column(children: [
                        if (error != null)
                          Semantics(liveRegion: true, child: Text(error!)),
                        if (loading) const CircularProgressIndicator(),
                        if (!loading && (nextCursor != null || error != null))
                          OutlinedButton(
                            onPressed: () => load(reset: nextCursor == null),
                            child:
                                Text(error == null ? 'Load more' : 'Try again'),
                          ),
                      ]);
                    }
                    final video = items[index];
                    return Card(
                        child: ListTile(
                      title: Text(video.title),
                      subtitle: video.description.isEmpty
                          ? null
                          : Text(video.description),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () {
                        final route = ScreenRoute(25, entityId: video.id);
                        Navigator.of(context)
                            .pushNamed(route.name, arguments: route);
                      },
                    ));
                  },
                ),
              );
            },
          )),
        ])),
        bottomNavigationBar: MainShell(
          navigation: (widget.catalog[widget.route.screen]
                  .named('Primary navigation') ??
              widget.catalog[17].named('Primary navigation'))!,
          screen: widget.route.screen,
          onSelected: navigate,
        ),
      );

  Widget _state(BuildContext context, String message,
          {required VoidCallback onRetry}) =>
      Center(
          child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.video_library_outlined,
                      size: 48, color: KoloVibeColors.navy),
                  const SizedBox(height: 16),
                  Text(message, textAlign: TextAlign.center),
                  const SizedBox(height: 16),
                  OutlinedButton(
                      onPressed: onRetry, child: const Text('Try again')),
                ],
              )));
}

class LiveVideoDetailScreen extends StatefulWidget {
  const LiveVideoDetailScreen(
      {super.key, required this.id, required this.repository, this.engagement});
  final String id;
  final LiveVideoRepository repository;
  final LiveVideoEngagementRepository? engagement;

  @override
  State<LiveVideoDetailScreen> createState() => _LiveVideoDetailScreenState();
}

class _LiveVideoDetailScreenState extends State<LiveVideoDetailScreen> {
  LiveVideo? item;
  Object? error;
  bool loading = true;
  LiveVideoEngagementController? engagementController;
  VideoPlayerController? player;
  String? playerError;
  bool? shownPlaying;

  @override
  void initState() {
    super.initState();
    if (widget.engagement != null) {
      engagementController =
          LiveVideoEngagementController(widget.engagement!, widget.id)
            ..addListener(_refresh);
      engagementController!.loadLike();
    }
    load();
  }

  void _refresh() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    player?.removeListener(_onPlaybackChanged);
    player?.dispose();
    engagementController?.removeListener(_refresh);
    engagementController?.dispose();
    super.dispose();
  }

  void _onPlaybackChanged() {
    final current = player;
    if (current == null || !mounted) return;
    final value = current.value;
    if (value.hasError) {
      if (playerError == null) {
        setState(() => playerError = 'Playback could not continue. Try again.');
      }
    } else {
      if (value.isPlaying || value.isCompleted) {
        engagementController?.reportProgress(value.position,
            completed: value.isCompleted);
      }
      if (shownPlaying != value.isPlaying) {
        setState(() => shownPlaying = value.isPlaying);
      }
    }
  }

  Future<void> _startPlayback() async {
    final controller = engagementController;
    if (controller == null) return;
    setState(() => playerError = null);
    final grant = await controller.startPlayback();
    if (!mounted || grant == null) return;
    final previous = player;
    player = null;
    shownPlaying = null;
    if (previous != null) {
      previous.removeListener(_onPlaybackChanged);
      await previous.dispose();
    }
    if (!mounted) return;
    final next = VideoPlayerController.networkUrl(grant.url);
    try {
      await next.initialize();
      if (!mounted) {
        await next.dispose();
        return;
      }
      player = next..addListener(_onPlaybackChanged);
      setState(() {});
      await next.play();
    } catch (_) {
      if (identical(player, next)) player = null;
      await next.dispose();
      if (mounted) {
        setState(() => playerError = 'Playback could not start. Try again.');
      }
    }
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final value = await widget.repository.detail(widget.id);
      if (mounted) setState(() => item = value);
    } on ApiFailure catch (failure) {
      if (mounted) setState(() => error = failure);
    } on FormatException catch (failure) {
      if (mounted) setState(() => error = failure);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Original')),
        body: SafeArea(child: Builder(
          builder: (context) {
            if (loading) {
              return const Center(child: CircularProgressIndicator());
            }
            if (error != null) {
              final failure = error;
              final missing = failure is ApiFailure && failure.status == 404;
              return Center(
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                Semantics(
                    liveRegion: true,
                    child: Text(missing
                        ? 'This original is not available for public viewing.'
                        : 'Videos are temporarily unavailable.')),
                if (!missing)
                  OutlinedButton(
                    onPressed: load,
                    child: const Text('Try again'),
                  ),
              ]));
            }
            final video = item!;
            return ListView(padding: const EdgeInsets.all(24), children: [
              Text(video.title,
                  style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 16),
              Text(video.description),
              if (engagementController case final controller?) ...[
                const SizedBox(height: 16),
                if (controller.likeBusy && controller.liked == null)
                  const LinearProgressIndicator(),
                if (controller.liked != null)
                  OutlinedButton.icon(
                    onPressed:
                        controller.likeBusy ? null : controller.toggleLike,
                    icon: Icon(controller.liked!
                        ? Icons.favorite
                        : Icons.favorite_border),
                    label: Text(controller.liked! ? 'Unlike' : 'Like'),
                  ),
                if (controller.likeError case final message?)
                  Semantics(liveRegion: true, child: Text(message)),
                if (controller.liked == null && !controller.likeBusy)
                  TextButton(
                    onPressed: controller.loadLike,
                    child: const Text('Retry like state'),
                  ),
              ],
              const SizedBox(height: 16),
              TextButton(
                  onPressed: () {
                    final route = ScreenRoute(38, entityId: video.creatorId);
                    Navigator.of(context)
                        .pushNamed(route.name, arguments: route);
                  },
                  child: const Text('View creator')),
              if (engagementController != null)
                TextButton.icon(
                  onPressed: () {
                    final route = ScreenRoute(71, entityId: video.id);
                    Navigator.of(context).pushNamed(route.name, arguments: route);
                  },
                  icon: const Icon(Icons.flag_outlined),
                  label: const Text('Report this video'),
                ),
              const SizedBox(height: 24),
              if (player case final current?
                  when current.value.isInitialized) ...[
                AspectRatio(
                  aspectRatio: current.value.aspectRatio,
                  child: VideoPlayer(current),
                ),
                const SizedBox(height: 8),
                TextButton.icon(
                  onPressed: () => current.value.isPlaying
                      ? current.pause()
                      : current.play(),
                  icon: Icon(
                      current.value.isPlaying ? Icons.pause : Icons.play_arrow),
                  label: Text(current.value.isPlaying ? 'Pause' : 'Play'),
                ),
                if (playerError case final message?) ...[
                  Semantics(liveRegion: true, child: Text(message)),
                  TextButton(
                    onPressed: _startPlayback,
                    child: const Text('Retry playback'),
                  ),
                ],
              ] else if (engagementController case final controller?) ...[
                FilledButton.icon(
                  onPressed: controller.playbackBusy ? null : _startPlayback,
                  icon: const Icon(Icons.play_arrow),
                  label: Text(controller.playbackBusy
                      ? 'Loading playback…'
                      : 'Play original'),
                ),
                if (controller.playbackError case final message?)
                  Semantics(liveRegion: true, child: Text(message)),
                if (playerError case final message?)
                  Semantics(liveRegion: true, child: Text(message)),
              ] else
                const Text('Sign in to watch this original.'),
            ]);
          },
        )),
      );
}
