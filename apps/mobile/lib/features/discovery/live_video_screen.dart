import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
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
import 'slow_connection_sheet.dart';

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
      this.creators,
      this.fullScreen = false,
      this.playerFactory,
      this.device = const PlatformDeviceBridge()});
  final String id;
  final LiveVideoRepository repository;
  final LiveVideoEngagementRepository? engagement;
  final LiveCreatorRepository? creators;
  final DeviceBridge device;
  final bool fullScreen;
  final VideoPlayerController Function(Uri)? playerFactory;

  @override
  State<LiveVideoDetailScreen> createState() => _LiveVideoDetailScreenState();
}

class _LiveVideoDetailScreenState extends State<LiveVideoDetailScreen>
    with WidgetsBindingObserver {
  LiveVideo? item;
  LiveCreator? creator;
  Object? error;
  bool loading = true;
  LiveVideoEngagementController? engagementController;
  VideoPlayerController? player;
  String? playerError;
  bool? shownPlaying;
  bool buffering = false, slow = false, starting = false, sharing = false;
  bool slowDismissed = false;
  int attempt = 0;
  bool likedToast = false;
  Timer? toastTimer;
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
    slowDismissed = false;
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
    if (controller.likeFailure == null && controller.liked == true) {
      toastTimer?.cancel();
      setState(() => likedToast = true);
      toastTimer = Timer(const Duration(seconds: 3), () {
        if (mounted) setState(() => likedToast = false);
      });
    }
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
      await _shareSheet(url);
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

  /// M-031 (404) and M-035 (403): the designed state layout. The text states
  /// only what the service reported; no alternative video is suggested unless
  /// the service lists one.
  Widget _unavailable(int status) => SingleChildScrollView(
      key: ValueKey(status == 403 ? 'M-035' : 'M-031'),
      padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        KoloMedallion(
            status == 403 ? KoloIcons.shieldAlert : KoloIcons.videoOff),
        const SizedBox(height: 24),
        KoloHeadline(
            status == 403
                ? 'This video is\nrestricted.'
                : 'This story isn’t\navailable right now.',
            size: 26),
        const SizedBox(height: 12),
        Text(
            status == 403
                ? 'This content isn’t available to your account under the current account or content rules.'
                : 'This original is not available for public viewing. It may have been unpublished, removed or made unavailable.',
            style: KoloVibeText.body(14, height: 1.5)),
        const SizedBox(height: 16),
        if (status == 403)
          const KoloNote(
              title: 'A safer viewing experience',
              message:
                  'We can only show information permitted by the content policy. This restriction cannot be bypassed.',
              asset: KoloIcons.info),
        FilledButton(
            onPressed: () => navigate(19),
            child: Text(status == 403
                ? 'Explore other videos'
                : 'Explore other originals')),
        const SizedBox(height: 12),
        if (status == 403)
          OutlinedButton(
              onPressed: () => navigate(87),
              child: const Text('Read community guidelines'))
        else ...[
          OutlinedButton(
              onPressed: () => Navigator.of(context).maybePop(),
              child: const Text('Go back')),
          _anotherStory(),
        ],
      ]));

  /// "Try another story": the newest public original other than this one, read
  /// from the service. Shown only when the service returns one.
  Widget _anotherStory() => FutureBuilder<LiveVideoPage>(
      future: widget.repository.filteredPage(),
      builder: (context, snapshot) {
        final other = snapshot.data?.items
            .where((video) => video.id != widget.id)
            .firstOrNull;
        if (other == null) return const SizedBox.shrink();
        return Padding(
            padding: const EdgeInsets.only(top: 24),
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const KoloHeadline('Try another story', size: 18),
              const SizedBox(height: 12),
              KoloVideoRow(
                  video: other,
                  meta: [
                    if (other.category != null) categoryLabel(other.category!),
                    if (formatDuration(other.durationMs) != null)
                      formatDuration(other.durationMs)!,
                  ].join(' · '),
                  onTap: () => navigate(25, other.id)),
            ]));
      });

  /// M-030: the designed share sheet. The share was already recorded and the
  /// link is the server's public video URL; the device sheet and the clipboard
  /// are the only destinations offered.
  Future<void> _shareSheet(Uri url) async {
    final title = item?.title ?? 'Original';
    final choice = await showModalBottomSheet<String>(
        context: context,
        routeSettings: RouteSettings(name: const ScreenRoute(30).name),
        isScrollControlled: true,
        // The feed is dark; the sheet keeps the light design surface.
        backgroundColor: Colors.white,
        builder: (sheet) => Theme(
            data: KoloVibeTheme.light(),
            child: SafeArea(
                child: SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
                    child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          const KoloHeadline('Share original stories',
                              size: 24),
                          const SizedBox(height: 16),
                          Container(
                              padding: const EdgeInsets.all(16),
                              decoration: BoxDecoration(
                                  color: Colors.white,
                                  borderRadius:
                                      BorderRadius.circular(KoloVibeRadii.tile),
                                  border:
                                      Border.all(color: KoloVibeColors.line)),
                              child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(title,
                                        maxLines: 2,
                                        overflow: TextOverflow.ellipsis,
                                        style: KoloVibeText.body(14,
                                            weight: FontWeight.w600,
                                            color: KoloVibeColors.navy)),
                                    const SizedBox(height: 4),
                                    Text('Public video link',
                                        style: KoloVibeText.body(12)),
                                  ])),
                          const SizedBox(height: 16),
                          FilledButton(
                              onPressed: () => Navigator.pop(sheet, 'device'),
                              child:
                                  const Text('Share link using a device app')),
                          const SizedBox(height: 12),
                          OutlinedButton.icon(
                              onPressed: () => Navigator.pop(sheet, 'copy'),
                              icon: const Icon(Icons.copy, size: 18),
                              label: const Text('Copy public link')),
                          const SizedBox(height: 12),
                          Text(
                              'Device share options vary. Shares a link, not a video download.',
                              style: KoloVibeText.body(11, height: 1.5)),
                          TextButton(
                              onPressed: () => Navigator.pop(sheet),
                              child: const Text('Cancel')),
                        ])))));
    if (!mounted || choice == null) return;
    if (choice == 'copy') {
      await Clipboard.setData(ClipboardData(text: url.toString()));
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Public link copied')));
      return;
    }
    final opened = await widget.device.share(url.toString());
    if (!mounted || opened) return;
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Native sharing is not available on this device.')));
  }

  Widget playbackState(Object failure,
      {bool media = false, bool metadata = false}) {
    final status = failure is ApiFailure ? failure.status : null;
    if (status == 401) {
      return FilledButton(
          onPressed: () => navigate(4), child: const Text('Sign in to watch'));
    }
    if (status == 403 || status == 404) {
      return _unavailable(status!);
    }
    if (media) {
      // M-033: the designed "Playback paused" card.
      return Container(
          key: const ValueKey('M-033'),
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
              color: KoloVibeColors.navy,
              borderRadius: BorderRadius.circular(KoloVibeRadii.card)),
          child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Playback paused',
                    style: KoloVibeText.heading(22, color: Colors.white)),
                const SizedBox(height: 8),
                Text(
                    'We couldn’t load this video. Check your network and try again.',
                    style: KoloVibeText.body(13,
                        color: const Color(0xFFD0D8E8), height: 1.5)),
                const SizedBox(height: 16),
                FilledButton(
                    onPressed: _startPlayback,
                    child: const Text('Retry playback')),
                TextButton(
                    onPressed: () => navigate(19),
                    style: TextButton.styleFrom(foregroundColor: Colors.white),
                    child: const Text('Explore other originals')),
              ]));
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
    toastTimer?.cancel();
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

  /// M-034: the person asked to try again while a slow start was still pending. The earlier
  /// attempt is abandoned (its controller is disposed when it finishes) and a fresh grant is used.
  Future<void> _retrySlow() async {
    starting = false;
    setBuffering(false);
    await _startPlayback();
  }

  Future<void> _startPlayback() async {
    if (starting) return;
    final mine = ++attempt;
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
      if (mounted && mine == attempt) {
        setBuffering(false);
        setState(() {
          playbackFailure = failure;
          starting = false;
        });
      }
      return;
    }
    if (!mounted || mine != attempt) return;
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
      if (!mounted || mine != attempt) {
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
      if (mounted && mine == attempt) {
        setBuffering(false);
        setState(() {
          starting = false;
          playerError = 'Playback could not start. Try again.';
        });
      }
    }
  }

  /// The handle is optional chrome: a failed lookup leaves the caption
  /// without it rather than blocking playback.
  Future<void> _loadCreator(String id) async {
    final repository = widget.creators;
    if (repository == null) return;
    try {
      final value = await repository.detail(id);
      if (mounted) setState(() => creator = value);
    } catch (_) {
      // No handle is shown.
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
        _loadCreator(value.creatorId);
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
            Image(
                image: posterProvider(video.posterUrl!),
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => const SizedBox()),
          const IgnorePointer(
              child: DecoratedBox(
                  decoration: BoxDecoration(
                      gradient: LinearGradient(
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                          stops: [
                0,
                .24,
                .58,
                1
              ],
                          colors: [
                Color(0xBB001539),
                Color(0x11001539),
                Color(0x22001539),
                Color(0xFA001539)
              ])))),
          if (likedToast)
            Positioned(
                top: 112,
                left: 20,
                child: Semantics(
                    liveRegion: true,
                    child: Container(
                        key: const ValueKey('M-029'),
                        padding: const EdgeInsets.symmetric(
                            horizontal: 14, vertical: 10),
                        decoration: BoxDecoration(
                            color: KoloVibeColors.navy,
                            borderRadius: BorderRadius.circular(12)),
                        child: Text('Liked · Tap heart to unlike',
                            style: KoloVibeText.body(12,
                                weight: FontWeight.w600,
                                color: Colors.white))))),
          if (buffering && !(slow && !slowDismissed))
            Center(
                child: Column(
                    mainAxisSize: MainAxisSize.min,
                    key: ValueKey(slow ? 'M-034' : 'M-032'),
                    children: [
                  const SizedBox(
                      width: 40,
                      height: 40,
                      child: CircularProgressIndicator(
                          strokeWidth: 3, color: Colors.white)),
                  const SizedBox(height: 12),
                  Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 10),
                      decoration: BoxDecoration(
                          color: const Color(0xCC001539),
                          borderRadius: BorderRadius.circular(12)),
                      child: Text(
                          slow
                              ? 'Still loading on a slow connection…'
                              : 'Preparing playback…',
                          textAlign: TextAlign.center,
                          style: KoloVibeText.body(13,
                              weight: FontWeight.w600, color: Colors.white))),
                ])),
          Positioned(
              left: 20,
              right: 96,
              bottom: 66,
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (creator != null) ...[
                      Text('@${creator!.handle}',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: KoloVibeText.heading(17, color: Colors.white)),
                      const SizedBox(height: 8),
                    ],
                    Text(video.title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: creator != null
                            ? KoloVibeText.body(15,
                                weight: FontWeight.w600, color: Colors.white)
                            : KoloVibeText.heading(17, color: Colors.white)),
                    if (video.description.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      Text(video.description,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: KoloVibeText.body(12, color: Colors.white)),
                    ],
                    if (video.category != null || video.tags.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      Text(
                          [
                            if (video.category != null)
                              categoryLabel(video.category!),
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
                      creator == null || creator!.displayName.isEmpty
                          ? const CircleAvatar(
                              radius: 22,
                              backgroundColor: Color(0xFF142D52),
                              child: Icon(Icons.person_outline,
                                  color: Colors.white))
                          : KoloAvatar(name: creator!.displayName, size: 44),
                      Positioned(
                          bottom: -8,
                          right: 10,
                          child: SvgPicture.asset('assets/images/feed/plus.svg',
                              width: 20, height: 20))
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
                      onPressed: () =>
                          current.setVolume(current.value.volume == 0 ? 1 : 0),
                      icon: SvgPicture.asset('assets/images/feed/volume.svg',
                          width: 18, height: 18)),
                ] else
                  const Expanded(child: SizedBox()),
              ])),
          if (playbackFailure != null || playerError != null)
            Center(
                child: Card(
                    child: playbackState(
                        playbackFailure ?? StateError('Playback failed'),
                        media: playerError != null))),
          // A slow-connection sheet is modal over the feed. Draw its scrim and
          // actions after the caption, rail and player controls so none of them
          // can paint over the sheet or intercept its buttons.
          if (buffering && slow && !slowDismissed) ...[
            const Positioned.fill(
                child: ColoredBox(color: Color(0x99001539))),
            Positioned(
                left: 0,
                right: 0,
                bottom: 0,
                child: SlowConnectionSheet(
                    key: const ValueKey('M-034'),
                    onRetry: _retrySlow,
                    onKeepWaiting: () => setState(() => slowDismissed = true))),
          ],
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
  }) =>
      SizedBox(
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

  /// M-070: the designed "Video options" sheet. Share uses the recorded share
  /// flow; Report opens the report journey (sign-in first when signed out).
  void _showFeedActions(LiveVideo video) {
    showModalBottomSheet<void>(
        context: context,
        routeSettings: RouteSettings(name: const ScreenRoute(70).name),
        isScrollControlled: true,
        // The feed is dark; the sheet keeps the light design surface.
        backgroundColor: Colors.white,
        builder: (sheetContext) => Theme(
            data: KoloVibeTheme.light(),
            child: SafeArea(
                child: SingleChildScrollView(
                    child: Padding(
                        padding: const EdgeInsets.fromLTRB(24, 0, 24, 16),
                        child: Column(
                            mainAxisSize: MainAxisSize.min,
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              const KoloHeadline('Video options', size: 24),
                              const SizedBox(height: 8),
                              KoloListRow(
                                  title: 'Share public link',
                                  icon: Icons.ios_share,
                                  onTap: () {
                                    Navigator.of(sheetContext).pop();
                                    share();
                                  }),
                              KoloListRow(
                                  title: 'Report this video',
                                  subtitle:
                                      'Tell us about a possible guideline concern',
                                  icon: Icons.flag_outlined,
                                  destructive: true,
                                  divider: false,
                                  onTap: () {
                                    Navigator.of(sheetContext).pop();
                                    navigate(
                                        widget.engagement == null ? 4 : 71,
                                        widget.engagement == null
                                            ? null
                                            : video.id);
                                  }),
                              const SizedBox(height: 8),
                              Text(
                                  'Reporting is private. Submitting a report does not automatically remove this video.',
                                  style: KoloVibeText.body(11, height: 1.5)),
                            ]))))));
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

  String get _pageTitle {
    final failure = error;
    final status = failure is ApiFailure ? failure.status : null;
    return status == 404
        ? 'Video unavailable'
        : status == 403
            ? 'Restricted video'
            : 'Original';
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        // The vertical feeds draw their own tabs over the video.
        appBar: widget.fullScreen
            ? null
            : AppBar(title: Text(_pageTitle), actions: [
                // Nothing to report when the video itself is unavailable.
                if (error == null)
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
                      if (creator != null) ...[
                        const SizedBox(height: 16),
                        KoloCreatorRow(
                            creator: creator!,
                            actionLabel: 'View',
                            onOpen: () => navigate(26, video.creatorId),
                            onFollow: () => navigate(26, video.creatorId)),
                      ],
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
                        Text(
                            'Published ${_date(video.publishedAt!)}${formatDuration(video.durationMs) == null ? '' : ' · ${formatDuration(video.durationMs)}'}',
                            style: Theme.of(context).textTheme.bodySmall),
                      ],
                      if (formatPlays(video.playCount) != null) ...[
                        const SizedBox(height: 4),
                        Text(formatPlays(video.playCount)!,
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
                      if (buffering && slow && !slowDismissed)
                        SlowConnectionSheet(
                            key: const ValueKey('M-034'),
                            inline: true,
                            onRetry: _retrySlow,
                            onKeepWaiting: () =>
                                setState(() => slowDismissed = true))
                      else if (buffering)
                        Column(
                            key: ValueKey(slow ? 'M-034' : 'M-032'),
                            children: [
                              Text(slow
                                  ? 'Still loading on a slow connection…'
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
                          child: Text(creator == null ||
                                  creator!.displayName.isEmpty
                              ? 'View creator'
                              : 'Visit ${creator!.displayName.split(' ').first}’s profile')),
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
