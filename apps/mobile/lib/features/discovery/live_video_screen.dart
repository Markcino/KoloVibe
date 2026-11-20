import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:video_player/video_player.dart';
import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import '../../core/platform/device_bridge.dart';
import '../system/system_ui.dart';
import '../../core/presentation/design_node.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../shell/main_shell.dart';
import '../../shared/widgets/kolo_components.dart';
import '../../shared/widgets/kolo_media.dart';
import 'home_dashboard.dart' show categoryLabel;
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
      {super.key,
      required this.id,
      required this.repository,
      this.engagement,
      this.fullScreen = false,
      this.playerFactory,
      this.device = const PlatformDeviceBridge()});
  final String id;
  final LiveVideoRepository repository;
  final LiveVideoEngagementRepository? engagement;
  final DeviceBridge device;
  final bool fullScreen;
  final VideoPlayerController Function(Uri)? playerFactory;

  @override
  State<LiveVideoDetailScreen> createState() => _LiveVideoDetailScreenState();
}

class _LiveVideoDetailScreenState extends State<LiveVideoDetailScreen>
    with WidgetsBindingObserver {
  LiveVideo? item;
  Object? error;
  bool loading = true;
  LiveVideoEngagementController? engagementController;
  VideoPlayerController? player;
  String? playerError;
  bool? shownPlaying;
  bool buffering = false, slow = false, starting = false, sharing = false;
  Timer? bufferTimer;
  Object? playbackFailure;
  void navigate(int screen, [String? id]) {
    player?.pause();
    final route = ScreenRoute(screen, entityId: id);
    Navigator.of(context).pushNamed(route.name, arguments: route);
  }

  void setBuffering(bool value) {
    if (buffering == value) return;
    bufferTimer?.cancel();
    buffering = value;
    slow = false;
    if (value) {
      bufferTimer = Timer(const Duration(seconds: 5), () {
        if (mounted && buffering) setState(() => slow = true);
      });
    }
    if (mounted) setState(() {});
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) player?.pause();
  }

  Future<void> toggleLike() async {
    final controller = engagementController;
    if (controller == null) {
      navigate(4);
      return;
    }
    await controller.toggleLike();
    if (!mounted) return;
    final failure = controller.likeFailure;
    if (failure is ApiFailure && failure.status == 401) navigate(4);
  }

  Future<void> share() async {
    if (sharing) return;
    if (widget.engagement == null) {
      navigate(4);
      return;
    }
    setState(() => sharing = true);
    try {
      final url = await widget.engagement!.share(widget.id);
      if (!mounted) return;
      final opened = await widget.device.share(url.toString());
      if (!mounted || opened) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Native sharing is not available on this device.')));
    } catch (failure) {
      if (!mounted) return;
      if (failure is ApiFailure && failure.status == 401) {
        navigate(4);
      } else {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text(
                'Sharing is unavailable right now. No share link was opened.')));
      }
    } finally {
      if (mounted) setState(() => sharing = false);
    }
  }

  Widget playbackState(Object failure,
      {bool media = false, bool metadata = false}) {
    final status = failure is ApiFailure ? failure.status : null;
    if (status == 401) {
      return FilledButton(
          onPressed: () => navigate(4), child: const Text('Sign in to watch'));
    }
    if (status == 403 || status == 404 || media) {
      return Column(
          key: ValueKey(status == 403
              ? 'M-035'
              : status == 404
                  ? 'M-031'
                  : 'M-033'),
          children: [
            Text(status == 403
                ? 'This video is restricted.'
                : status == 404
                    ? 'This original is not available for public viewing.'
                    : 'Playback paused. We couldn’t load this video.'),
            if (status != 403 && status != 404)
              TextButton(
                  onPressed: _startPlayback,
                  child: const Text('Retry playback')),
            TextButton(
                onPressed: () => navigate(19),
                child: const Text('Explore other originals')),
            if (status == 403)
              TextButton(
                  onPressed: () => navigate(87),
                  child: const Text('Read community guidelines')),
          ]);
    }
    return SystemFailureView(
        error: failure,
        onRetry: metadata ? load : _startPlayback,
        onSignIn: () => navigate(4));
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
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
    WidgetsBinding.instance.removeObserver(this);
    bufferTimer?.cancel();
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
    setBuffering(value.isBuffering);
    if (value.hasError) {
      setBuffering(false);
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
    if (starting) return;
    setState(() {
      starting = true;
      playerError = null;
      playbackFailure = null;
    });
    setBuffering(true);
    PlaybackGrant? grant;
    try {
      if (engagementController != null) {
        await widget.repository
            .playback(widget.id, account: widget.engagement!.account);
        grant = await engagementController!.startPlayback();
        if (grant == null) {
          throw engagementController!.playbackFailure ??
              const FormatException('Invalid playback');
        }
      } else {
        grant = await widget.repository.playback(widget.id);
      }
    } catch (failure) {
      if (mounted) {
        setBuffering(false);
        setState(() {
          playbackFailure = failure;
          starting = false;
        });
      }
      return;
    }
    if (!mounted) return;
    final previous = player;
    player = null;
    shownPlaying = null;
    if (previous != null) {
      previous.removeListener(_onPlaybackChanged);
      await previous.dispose();
    }
    if (!mounted) return;
    final next = widget.playerFactory?.call(grant.url) ??
        VideoPlayerController.networkUrl(grant.url);
    try {
      await next.initialize().timeout(const Duration(seconds: 15));
      if (!mounted) {
        await next.dispose();
        return;
      }
      player = next..addListener(_onPlaybackChanged);
      setState(() {});
      setBuffering(false);
      setState(() => starting = false);
      await next.play();
    } catch (_) {
      if (identical(player, next)) player = null;
      await next.dispose();
      if (mounted) {
        setBuffering(false);
        setState(() {
          starting = false;
          playerError = 'Playback could not start. Try again.';
        });
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
      if (mounted) {
        setState(() => item = value);
        if (widget.fullScreen) _startPlayback();
      }
    } on ApiFailure catch (failure) {
      if (mounted) setState(() => error = failure);
    } on FormatException catch (failure) {
      if (mounted) setState(() => error = failure);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Widget fullScreen(LiveVideo video) {
    final current = player;
    final controller = engagementController;
    return ColoredBox(
        color: Colors.black,
        child: Stack(fit: StackFit.expand, children: [
          if (current != null && current.value.isInitialized)
            Center(
                child: AspectRatio(
                    aspectRatio: current.value.aspectRatio,
                    child: VideoPlayer(current)))
          else if (video.posterUrl != null)
            Image.network(video.posterUrl.toString(),
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => const SizedBox()),
          const IgnorePointer(
              child: DecoratedBox(
                  decoration: BoxDecoration(
                      gradient: LinearGradient(
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                          stops: [0, .24, .58, 1],
                          colors: [
                        Color(0xBB001539),
                        Color(0x11001539),
                        Color(0x22001539),
                        Color(0xFA001539)
                      ])))),
          if (buffering)
            Center(
                child: Card(
                    child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                            mainAxisSize: MainAxisSize.min,
                            key: ValueKey(slow ? 'M-034' : 'M-032'),
                            children: [
                              Text(slow
                                  ? 'Slow connection. No lower-data rendition is available to select.'
                                  : 'Preparing playback…'),
                              const LinearProgressIndicator(),
                            ])))),
          if (playbackFailure != null || playerError != null)
            Center(
                child: Card(
                    child: playbackState(
                        playbackFailure ?? StateError('Playback failed'),
                        media: playerError != null))),
          Positioned(
              left: 20,
              right: 96,
              bottom: 66,
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(video.title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: KoloVibeText.heading(17, color: Colors.white)),
                    if (video.description.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      Text(video.description,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: KoloVibeText.body(12, color: Colors.white)),
                    ],
                    if (video.category != null || video.tags.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      Text([
                        if (video.category != null) categoryLabel(video.category!),
                        ...video.tags.map((tag) => '#$tag')
                      ].join(' · '),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: KoloVibeText.body(11,
                              color: const Color(0xFFA8B7D0))),
                    ]
                  ])),
          Positioned(
              right: 14,
              bottom: 96,
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                IconButton(
                    tooltip: 'View creator to follow',
                    onPressed: () => navigate(26, video.creatorId),
                    icon: Stack(clipBehavior: Clip.none, children: [
                      const CircleAvatar(
                          radius: 22,
                          backgroundColor: Color(0xFF142D52),
                          child: Icon(Icons.person_outline,
                              color: Colors.white)),
                      Positioned(
                          bottom: -8,
                          right: 10,
                          child: SvgPicture.asset(
                              'assets/images/feed/plus.svg',
                              width: 20,
                              height: 20))
                    ])),
                const SizedBox(height: 16),
                _feedAction(
                    asset: 'heart.svg',
                    label: controller?.liked == true ? 'Unlike' : 'Like',
                    caption: controller?.likeCount?.toString() ??
                        video.likeCount?.toString(),
                    active: controller?.liked == true,
                    onPressed: controller?.liked == null
                        ? () => navigate(4)
                        : controller!.likeBusy
                            ? null
                            : toggleLike),
                const SizedBox(height: 12),
                _feedAction(
                    asset: 'share.svg',
                    label: 'Share',
                    onPressed: sharing ? null : share),
                const SizedBox(height: 12),
                _feedAction(
                    asset: 'more.svg',
                    label: 'More',
                    onPressed: () => _showFeedActions(video)),
              ])),
          Positioned(
              left: 20,
              right: 20,
              bottom: 8,
              child: Row(children: [
                IconButton(
                    tooltip: current?.value.isPlaying == true
                        ? 'Pause video'
                        : 'Play video',
                    onPressed: current == null || !current.value.isInitialized
                        ? null
                        : () => current.value.isPlaying
                            ? current.pause()
                            : current.play(),
                    icon: SvgPicture.asset('assets/images/feed/pause.svg',
                        width: 18, height: 18)),
                if (current != null && current.value.isInitialized) ...[
                  ValueListenableBuilder<VideoPlayerValue>(
                      valueListenable: current,
                      builder: (_, value, __) => Text(
                          '${_playbackTime(value.position)} / ${_playbackTime(value.duration)}',
                          style: KoloVibeText.body(10, color: Colors.white))),
                  const SizedBox(width: 10),
                  Expanded(
                      child: VideoProgressIndicator(current,
                          allowScrubbing: false,
                          colors: const VideoProgressColors(
                              playedColor: KoloVibeColors.red,
                              bufferedColor: Color(0x66FFFFFF),
                              backgroundColor: Color(0xFFA8B7D0)))),
                  IconButton(
                      tooltip: current.value.volume == 0
                          ? 'Unmute video'
                          : 'Mute video',
                      onPressed: () => current.setVolume(
                          current.value.volume == 0 ? 1 : 0),
                      icon: SvgPicture.asset('assets/images/feed/volume.svg',
                          width: 18, height: 18)),
                ] else
                  const Expanded(child: SizedBox()),
              ])),
        ]));
  }

  String _playbackTime(Duration value) =>
      '${value.inMinutes.toString().padLeft(2, '0')}:${(value.inSeconds % 60).toString().padLeft(2, '0')}';

  Widget _feedAction({
    required String asset,
    required String label,
    required VoidCallback? onPressed,
    String? caption,
    bool active = false,
  }) => SizedBox(
        width: 50,
        child: Column(children: [
          IconButton(
              tooltip: label,
              onPressed: onPressed,
              icon: SvgPicture.asset('assets/images/feed/$asset',
                  width: 28,
                  height: 28,
                  colorFilter: active
                      ? const ColorFilter.mode(
                          KoloVibeColors.red, BlendMode.srcIn)
                      : null)),
          Text(caption ?? label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: KoloVibeText.body(11, color: Colors.white)),
        ]),
      );

  void _showFeedActions(LiveVideo video) {
    showModalBottomSheet<void>(
        context: context,
        builder: (sheetContext) => SafeArea(
            child: ListTile(
                leading: const Icon(Icons.flag_outlined),
                title: const Text('Report video'),
                onTap: () {
                  Navigator.of(sheetContext).pop();
                  navigate(widget.engagement == null ? 4 : 71,
                      widget.engagement == null ? null : video.id);
                })));
  }

  static const _months = [
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December'
  ];
  String _date(DateTime value) {
    final utc = value.toUtc();
    return '${utc.day} ${_months[utc.month - 1]} ${utc.year}';
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        // The vertical feeds draw their own tabs over the video.
        appBar: widget.fullScreen
            ? null
            : AppBar(title: const Text('Original'), actions: [
                PopupMenuButton<String>(
                    onSelected: (_) => navigate(
                        widget.engagement == null ? 4 : 71,
                        widget.engagement == null ? null : widget.id),
                    itemBuilder: (_) => [
                          const PopupMenuItem(
                              value: 'report', child: Text('Report video'))
                        ])
              ]),
        body: SafeArea(child: Builder(
          builder: (context) {
            if (loading) {
              return const Center(child: CircularProgressIndicator());
            }
            if (error != null) {
              return playbackState(error!, metadata: true);
            }
            final video = item!;
            if (widget.fullScreen) return fullScreen(video);
            return SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(video.title,
                          style: Theme.of(context).textTheme.headlineMedium),
                      const SizedBox(height: 16),
                      if (player == null)
                        ClipRRect(
                            borderRadius:
                                BorderRadius.circular(KoloVibeRadii.card),
                            child: AspectRatio(
                                aspectRatio: 16 / 9,
                                child: KoloPoster(
                                    url: video.posterUrl, iconSize: 44))),
                      if (video.description.isNotEmpty) ...[
                        const SizedBox(height: 16),
                        Text(video.description,
                            style: Theme.of(context).textTheme.bodyLarge),
                      ],
                      const SizedBox(height: 16),
                      Wrap(spacing: 8, runSpacing: 8, children: [
                        KoloBadge(video.category == null
                            ? 'Original'
                            : categoryLabel(video.category!)),
                        for (final tag in video.tags) KoloBadge('#$tag'),
                      ]),
                      if (video.publishedAt != null) ...[
                        const SizedBox(height: 12),
                        Text('Published ${_date(video.publishedAt!)}',
                            style: Theme.of(context).textTheme.bodySmall),
                      ],
                      const SizedBox(height: 4),
                      Text(
                          '${engagementController?.likeCount ?? video.likeCount ?? 'Unavailable'} likes',
                          style: KoloVibeText.body(14,
                              weight: FontWeight.w600,
                              color: KoloVibeColors.navy)),
                      const SizedBox(height: 16),
                      OutlinedButton(
                          onPressed: sharing ? null : share,
                          child: const Text('Share')),
                      if (buffering)
                        Column(
                            key: ValueKey(slow ? 'M-034' : 'M-032'),
                            children: [
                              Text(slow
                                  ? 'Playback is taking longer on this connection. No lower-data rendition is available to select.'
                                  : 'Preparing playback…'),
                              const LinearProgressIndicator(),
                            ]),
                      if (playbackFailure != null)
                        playbackState(playbackFailure!),
                      if (playerError != null)
                        playbackState(StateError('Playback failed'),
                            media: true),
                      if (engagementController case final controller?) ...[
                        const SizedBox(height: 16),
                        if (controller.likeBusy && controller.liked == null)
                          const LinearProgressIndicator(),
                        if (controller.liked != null)
                          OutlinedButton.icon(
                            onPressed: controller.likeBusy ? null : toggleLike,
                            icon: Icon(controller.liked!
                                ? Icons.favorite
                                : Icons.favorite_border),
                            label: Text(controller.liked! ? 'Unlike' : 'Like'),
                          ),
                        if (controller.likeError case final message?)
                          Semantics(liveRegion: true, child: Text(message)),
                        if (controller.liked == null && !controller.likeBusy)
                          TextButton(
                              onPressed: () =>
                                  controller.likeFailure is ApiFailure &&
                                          (controller.likeFailure as ApiFailure)
                                                  .status ==
                                              401
                                      ? navigate(4)
                                      : controller.loadLike(),
                              child: const Text('Like')),
                      ],
                      const SizedBox(height: 16),
                      OutlinedButton(
                          onPressed: () => navigate(26, video.creatorId),
                          child: const Text('View creator')),
                      if (engagementController != null)
                        TextButton.icon(
                          onPressed: () => navigate(71, video.id),
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
                          icon: Icon(current.value.isPlaying
                              ? Icons.pause
                              : Icons.play_arrow),
                          label:
                              Text(current.value.isPlaying ? 'Pause' : 'Play'),
                        ),
                        if (playerError case final message?) ...[
                          Semantics(liveRegion: true, child: Text(message)),
                          TextButton(
                            onPressed: _startPlayback,
                            child: const Text('Retry playback'),
                          ),
                        ],
                      ] else if (engagementController
                          case final controller?) ...[
                        FilledButton.icon(
                          onPressed:
                              controller.playbackBusy ? null : _startPlayback,
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
                        FilledButton(
                            onPressed: starting ? null : _startPlayback,
                            child: const Text('Play original')),
                      if (widget.engagement == null)
                        TextButton(
                            onPressed: () => navigate(4),
                            child: const Text('Sign in to like')),
                    ]));
          },
        )),
      );
}
