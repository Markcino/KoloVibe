import 'package:flutter/material.dart';
import '../../core/network/api_client.dart';
import '../../core/presentation/design_node.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/kolo_components.dart';
import '../account/live_account_repository.dart';
import '../creators/live_creator_repository.dart';
import '../shell/main_shell.dart';
import 'live_video_repository.dart';

typedef HomeNavigate = void Function(int screen, [String? id]);

/// Display label for a category slug such as `short_films`.
String categoryLabel(String slug) {
  final text = slug.replaceAll('_', ' ');
  return text.isEmpty ? text : text[0].toUpperCase() + text.substring(1);
}

String _greeting(DateTime time) => time.hour < 12
    ? 'Good morning'
    : time.hour < 17
        ? 'Good afternoon'
        : 'Good evening';

enum _Load { loading, ready, failed }

class _FollowState {
  _FollowState({this.following});
  bool? following;
  bool busy = false;
}

/// Home (M-017). Every block reads real service data and owns its own loading,
/// empty, error and signed-out state, so one failing request never hides the
/// rest of the screen. Nothing on this screen is sample content.
class HomeDashboard extends StatefulWidget {
  const HomeDashboard({
    super.key,
    required this.videos,
    required this.catalog,
    required this.navigate,
    required this.openCategory,
    this.creators,
    this.account,
    this.clock = DateTime.now,
  });
  final LiveVideoRepository videos;
  final LiveCreatorRepository? creators;
  final LiveAccountRepository? account;
  final DesignCatalog catalog;
  final HomeNavigate navigate;
  final ValueChanged<String> openCategory;
  final DateTime Function() clock;

  @override
  State<HomeDashboard> createState() => _HomeDashboardState();
}

class _HomeDashboardState extends State<HomeDashboard> {
  int generation = 0;
  bool signedOut = false;

  _Load accountLoad = _Load.loading;
  LiveAccount? user;

  _Load trendingLoad = _Load.loading;
  Object? trendingError;
  List<LiveVideo> trending = const [];

  _Load creatorsLoad = _Load.loading;
  final creatorById = <String, LiveCreator>{};
  final follows = <String, _FollowState>{};

  _Load followingLoad = _Load.loading;
  Object? followingError;
  List<LiveVideo> followingItems = const [];

  @override
  void initState() {
    super.initState();
    signedOut = widget.account == null;
    load();
  }

  @override
  void dispose() {
    generation++;
    super.dispose();
  }

  bool _isSignedOutFailure(Object failure) =>
      failure is ApiFailure && failure.status == 401;

  Future<void> load() async {
    final token = ++generation;
    bool current() => mounted && token == generation;
    setState(() {
      accountLoad = trendingLoad = creatorsLoad = followingLoad = _Load.loading;
      trendingError = followingError = null;
      trending = followingItems = const [];
      creatorById.clear();
      follows.clear();
      signedOut = widget.account == null;
    });
    await Future.wait([
      _loadAccount(current),
      _loadTrending(current),
      _loadFollowing(current),
    ]);
  }

  Future<void> _loadAccount(bool Function() current) async {
    final repository = widget.account;
    if (repository == null) {
      if (current()) setState(() => accountLoad = _Load.ready);
      return;
    }
    try {
      final value =
          repository.takeRestoredAccount() ?? await repository.currentAccount();
      if (!current()) return;
      setState(() {
        user = value;
        if (value == null) signedOut = true;
        accountLoad = _Load.ready;
      });
    } catch (failure) {
      if (!current()) return;
      setState(() {
        user = null;
        if (_isSignedOutFailure(failure)) signedOut = true;
        accountLoad = _Load.failed;
      });
    }
  }

  Future<void> _loadTrending(bool Function() current) async {
    try {
      final page = await widget.videos.filteredPage(sort: 'trending');
      if (!current()) return;
      setState(() {
        trending = page.items;
        trendingLoad = _Load.ready;
      });
    } catch (failure) {
      if (!current()) return;
      setState(() {
        trendingError = failure;
        trendingLoad = _Load.failed;
        creatorsLoad = _Load.ready;
      });
      return;
    }
    await _loadCreators(current);
  }

  Future<void> _loadCreators(bool Function() current) async {
    final repository = widget.creators;
    final ids = <String>[];
    for (final video in trending.take(6)) {
      if (!ids.contains(video.creatorId)) ids.add(video.creatorId);
      if (ids.length == 4) break;
    }
    if (repository == null || ids.isEmpty) {
      if (current()) setState(() => creatorsLoad = _Load.ready);
      return;
    }
    final results = await Future.wait(ids.map((id) async {
      try {
        return await repository.detail(id);
      } catch (_) {
        return null;
      }
    }));
    if (!current()) return;
    final loaded = results.whereType<LiveCreator>().toList();
    setState(() {
      for (final creator in loaded) {
        creatorById[creator.id] = creator;
      }
      creatorsLoad = loaded.isEmpty ? _Load.failed : _Load.ready;
    });
    if (widget.account != null && !signedOut) {
      await Future.wait(
          loaded.take(2).map((c) => _loadFollowState(c, current)));
    }
  }

  Future<void> _loadFollowState(
      LiveCreator creator, bool Function() current) async {
    try {
      final result = await widget.account!
          .authenticatedRequest('/creators/${creator.id}/follow');
      if (!current()) return;
      final value = result['following'];
      setState(() {
        if (result['creator_id'] == creator.id && value is bool) {
          follows[creator.id] = _FollowState(following: value);
        }
      });
    } catch (failure) {
      if (current() && _isSignedOutFailure(failure)) {
        setState(() => signedOut = true);
      }
    }
  }

  Future<void> _loadFollowing(bool Function() current) async {
    final repository = widget.account;
    if (repository == null) {
      if (current()) setState(() => followingLoad = _Load.ready);
      return;
    }
    try {
      final page = await widget.videos.followingPage(repository);
      if (!current()) return;
      setState(() {
        followingItems = page.items;
        followingLoad = _Load.ready;
      });
    } catch (failure) {
      if (!current()) return;
      setState(() {
        if (_isSignedOutFailure(failure)) {
          signedOut = true;
          followingLoad = _Load.ready;
        } else {
          followingError = failure;
          followingLoad = _Load.failed;
        }
      });
    }
  }

  Future<void> toggleFollow(LiveCreator creator) async {
    final repository = widget.account;
    final state = follows[creator.id];
    if (repository == null || signedOut) {
      widget.navigate(4);
      return;
    }
    if (state == null) {
      await _loadFollowState(creator, () => mounted);
      if (follows[creator.id] == null && mounted && !signedOut) {
        _message('Follow status could not be loaded. Try again.');
      } else if (signedOut) {
        widget.navigate(4);
      }
      return;
    }
    if (state.busy) return;
    final before = state.following!;
    setState(() {
      state.following = !before;
      state.busy = true;
    });
    try {
      final result = await repository.authenticatedRequest(
          '/creators/${creator.id}/follow',
          method: before ? 'DELETE' : 'PUT');
      if (result['creator_id'] != creator.id ||
          result['following'] != !before) {
        throw const FormatException('Invalid follow response');
      }
    } catch (failure) {
      if (!mounted) return;
      setState(() => state.following = before);
      if (_isSignedOutFailure(failure)) {
        widget.navigate(4);
      } else {
        _message('The follow change could not be confirmed. Try again.');
      }
    } finally {
      if (mounted) setState(() => state.busy = false);
    }
  }

  void _message(String text) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));

  String _creatorName(String id) {
    final creator = creatorById[id];
    if (creator == null) return '';
    return creator.displayName.isEmpty
        ? '@${creator.handle}'
        : creator.displayName;
  }

  String _likes(int count) {
    final text = count >= 1000000
        ? '${(count / 1000000).toStringAsFixed(1)}M'
        : count >= 1000
            ? '${(count / 1000).toStringAsFixed(1)}K'
            : '$count';
    return '${text.replaceAll('.0', '')} ${count == 1 ? 'like' : 'likes'}';
  }

  String _meta(LiveVideo video, {bool likes = false}) => [
        _creatorName(video.creatorId),
        if (video.category != null) categoryLabel(video.category!),
        if (likes && video.likeCount != null) _likes(video.likeCount!),
      ].where((part) => part.isNotEmpty).join(' · ');

  @override
  Widget build(BuildContext context) {
    final name = user?.displayName.trim() ?? '';
    final greeting = signedOut
        ? 'Welcome to KoloVibe'
        : name.isEmpty
            ? _greeting(widget.clock())
            : '${_greeting(widget.clock())}, $name';
    final morning = !signedOut && widget.clock().hour < 12;
    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: Column(children: [
          ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 60),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
              child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Flexible(child: KoloWordmark()),
                    if (signedOut)
                      KoloPillButton(
                          label: 'Sign in', onPressed: () => widget.navigate(4))
                    else
                      KoloAvatar(
                        name: name,
                        size: 36,
                        semanticLabel: 'My account',
                        onTap: () => widget.navigate(79),
                      ),
                  ]),
            ),
          ),
          Expanded(
            child: RefreshIndicator(
              color: KoloVibeColors.red,
              onRefresh: load,
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(24, 8, 24, 20),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      if (accountLoad == _Load.loading && !signedOut)
                        const Padding(
                            padding: EdgeInsets.symmetric(vertical: 6),
                            child: Align(
                                alignment: Alignment.centerLeft,
                                child: KoloSkeleton(width: 230, height: 26)))
                      else
                        Semantics(
                          header: true,
                          child: Text(morning ? '$greeting ☀️' : greeting,
                              style: KoloVibeText.heading(25, height: 1.15)),
                        ),
                      const SizedBox(height: 10),
                      KoloSearchBar(
                          hint: 'Search videos, creators…',
                          onTap: () => widget.navigate(21)),
                      const SizedBox(height: 10),
                      _hero(),
                      const SizedBox(height: 10),
                      IntrinsicHeight(
                        child: Row(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              Expanded(
                                  child: KoloServiceTile(
                                      asset:
                                          'assets/images/2b2fbc8bd11cb2049e08.svg',
                                      label: 'Videos',
                                      onTap: () => widget.navigate(24))),
                              const SizedBox(width: 8),
                              Expanded(
                                  child: KoloServiceTile(
                                      asset:
                                          'assets/images/8adb0dc5f78062f3b23e.svg',
                                      label: 'Explore',
                                      onTap: () => widget.navigate(19))),
                              const SizedBox(width: 8),
                              Expanded(
                                  child: KoloServiceTile(
                                      asset:
                                          'assets/images/c52a5c2dc75b4f67eb50.svg',
                                      label: 'Creator Studio',
                                      onTap: () => widget.navigate(37))),
                            ]),
                      ),
                      const SizedBox(height: 18),
                      KoloSectionHeading(
                          title: 'Creators to know',
                          actionLabel: 'See all',
                          onAction: () => widget.navigate(21)),
                      const SizedBox(height: 10),
                      ..._creators(),
                      ..._trendingRow(),
                      const SizedBox(height: 18),
                      KoloSectionHeading(
                          title: 'Following',
                          actionLabel: signedOut ? null : 'See all',
                          onAction: () => widget.navigate(18)),
                      const SizedBox(height: 10),
                      ..._following(),
                      const SizedBox(height: 18),
                      Wrap(spacing: 8, runSpacing: 8, children: [
                        for (final slug in videoCategories)
                          KoloChip(
                              label: categoryLabel(slug),
                              onTap: () => widget.openCategory(slug)),
                      ]),
                      const SizedBox(height: 14),
                      Text(
                          'Original voices. More approved services as available.',
                          style: KoloVibeText.body(11, height: 1.48)),
                    ]),
              ),
            ),
          ),
        ]),
      ),
      bottomNavigationBar: MainShell(
        navigation: widget.catalog[17].named('Primary navigation')!,
        screen: 17,
        onSelected: (target) => widget.navigate(target),
      ),
    );
  }

  Widget _hero() {
    if (trendingLoad == _Load.loading) {
      return const KoloSkeleton(height: 212, radius: KoloVibeRadii.card);
    }
    if (trendingLoad == _Load.failed) {
      return KoloInlineState(
          title: 'Trending is unavailable',
          message: _failureMessage(trendingError),
          icon: Icons.cloud_off_outlined,
          actionLabel: 'Try again',
          onAction: load);
    }
    if (trending.isEmpty) {
      return const KoloInlineState(
          title: 'No trending originals yet',
          message: 'Published originals will appear here.',
          icon: Icons.local_fire_department_outlined);
    }
    final video = trending.first;
    final meta = _meta(video);
    return _HeroCard(
      video: video,
      meta: meta.isEmpty ? 'Original' : meta,
      onTap: () => widget.navigate(25, video.id),
    );
  }

  List<Widget> _creators() {
    if (trendingLoad == _Load.failed) {
      return const [
        KoloInlineState(
            title: 'Creators are unavailable',
            message: 'They load together with trending. Try again above.',
            icon: Icons.people_outline)
      ];
    }
    if (trendingLoad == _Load.loading || creatorsLoad == _Load.loading) {
      return [
        const Row(children: [
          KoloSkeleton(width: 44, height: 44, radius: 22),
          SizedBox(width: 12),
          Expanded(child: KoloSkeleton(height: 36)),
        ])
      ];
    }
    final shown = <LiveCreator>[
      for (final video in trending)
        if (creatorById[video.creatorId] != null &&
            creatorById[video.creatorId]!.id != user?.id)
          creatorById[video.creatorId]!,
    ].fold<List<LiveCreator>>([], (list, creator) {
      if (list.length < 2 && !list.any((c) => c.id == creator.id)) {
        list.add(creator);
      }
      return list;
    });
    if (creatorsLoad == _Load.failed) {
      return [
        KoloInlineState(
            title: 'Creators could not be loaded',
            message: 'Check your connection, then try again.',
            icon: Icons.people_outline,
            actionLabel: 'Try again',
            onAction: load)
      ];
    }
    if (shown.isEmpty) {
      return const [
        KoloInlineState(
            title: 'No creators to show yet',
            message: 'Creators with published originals will appear here.',
            icon: Icons.people_outline)
      ];
    }
    return [
      for (final creator in shown) ...[
        _CreatorRow(
          creator: creator,
          following: follows[creator.id]?.following,
          busy: follows[creator.id]?.busy ?? false,
          onOpen: () => widget.navigate(26, creator.id),
          onFollow: () => toggleFollow(creator),
        ),
        const SizedBox(height: 8),
      ],
    ];
  }

  List<Widget> _trendingRow() {
    if (trendingLoad != _Load.ready || trending.length < 2) return const [];
    final video = trending[1];
    return [
      _VideoRow(
        kicker: 'TRENDING ORIGINAL',
        video: video,
        meta: _meta(video, likes: true),
        onTap: () => widget.navigate(25, video.id),
      ),
    ];
  }

  List<Widget> _following() {
    if (signedOut) {
      return [
        KoloInlineState(
            title: 'Sign in to see who you follow',
            message: 'Originals from creators you follow appear here.',
            icon: Icons.lock_outline,
            actionLabel: 'Sign in',
            onAction: () => widget.navigate(4))
      ];
    }
    if (followingLoad == _Load.loading) {
      return const [KoloSkeleton(height: 60)];
    }
    if (followingLoad == _Load.failed) {
      return [
        KoloInlineState(
            title: 'Following is unavailable',
            message: _failureMessage(followingError),
            icon: Icons.cloud_off_outlined,
            actionLabel: 'Try again',
            onAction: load)
      ];
    }
    if (followingItems.isEmpty) {
      return const [
        KoloInlineState(
            title: 'Nothing here yet',
            message: 'Follow creators to see their originals here.',
            icon: Icons.person_add_alt_outlined)
      ];
    }
    return [
      for (final video in followingItems.take(2)) ...[
        _VideoRow(
          kicker: 'FROM CREATORS YOU FOLLOW',
          video: video,
          meta: _meta(video, likes: true),
          onTap: () => widget.navigate(25, video.id),
        ),
        const SizedBox(height: 8),
      ],
    ];
  }

  String _failureMessage(Object? failure) {
    if (failure is ApiFailure && failure.offline) {
      return 'Check your connection, then try again.';
    }
    if (failure is ApiFailure && failure.status == 429) {
      return 'Too many requests. Wait a moment, then try again.';
    }
    return 'This could not be loaded right now. Try again.';
  }
}

class _Poster extends StatelessWidget {
  const _Poster({required this.url, this.iconSize = 28});
  final Uri? url;
  final double iconSize;

  @override
  Widget build(BuildContext context) {
    final fallback = DecoratedBox(
      decoration: const BoxDecoration(
          gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [KoloVibeColors.navy, KoloVibeColors.deepNavy])),
      child: Center(
          child: Icon(Icons.play_circle_outline,
              color: Colors.white54, size: iconSize)),
    );
    if (url == null) return fallback;
    return Image.network(url.toString(),
        fit: BoxFit.cover,
        excludeFromSemantics: true,
        errorBuilder: (_, __, ___) => fallback,
        loadingBuilder: (_, child, progress) =>
            progress == null ? child : fallback);
  }
}

class _HeroCard extends StatelessWidget {
  const _HeroCard(
      {required this.video, required this.meta, required this.onTap});
  final LiveVideo video;
  final String meta;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        label: 'Play ${video.title}. $meta',
        excludeSemantics: true,
        child: ClipRRect(
          borderRadius: BorderRadius.circular(KoloVibeRadii.card),
          child: Material(
            color: KoloVibeColors.navy,
            child: InkWell(
              onTap: onTap,
              child: Stack(children: [
                Positioned.fill(child: _Poster(url: video.posterUrl)),
                const Positioned.fill(
                    child: DecoratedBox(
                        decoration: BoxDecoration(
                            gradient: LinearGradient(
                                begin: Alignment.topCenter,
                                end: Alignment.bottomCenter,
                                colors: [
                      Color(0x21001539),
                      Color(0xF5001539)
                    ])))),
                ConstrainedBox(
                  constraints: const BoxConstraints(minHeight: 212),
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(18, 72, 18, 18),
                    child: Column(
                        mainAxisAlignment: MainAxisAlignment.end,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('KOLOVIBE ORIGINAL',
                              style: KoloVibeText.body(10,
                                  weight: FontWeight.w700,
                                  color: KoloVibeColors.gold,
                                  letterSpacing: 0.6)),
                          const SizedBox(height: 8),
                          Text(video.title,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: KoloVibeText.heading(27,
                                  color: Colors.white, height: 1.15)),
                          const SizedBox(height: 8),
                          Text(meta,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: KoloVibeText.body(11,
                                  color: Colors.white, height: 1.48)),
                        ]),
                  ),
                ),
                Positioned(
                  top: 16,
                  right: 18,
                  child: Container(
                    width: 42,
                    height: 42,
                    decoration: const BoxDecoration(
                        color: Colors.white, shape: BoxShape.circle),
                    child: const Icon(Icons.play_arrow_rounded,
                        color: KoloVibeColors.navy, size: 26),
                  ),
                ),
              ]),
            ),
          ),
        ),
      );
}

class _CreatorRow extends StatelessWidget {
  const _CreatorRow(
      {required this.creator,
      required this.following,
      required this.busy,
      required this.onOpen,
      required this.onFollow});
  final LiveCreator creator;
  final bool? following;
  final bool busy;
  final VoidCallback onOpen, onFollow;

  @override
  Widget build(BuildContext context) {
    final name = creator.displayName.isEmpty
        ? '@${creator.handle}'
        : creator.displayName;
    final detail = [
      if (creator.displayName.isNotEmpty) '@${creator.handle}',
      if (creator.location.isNotEmpty) creator.location,
    ].join(' · ');
    return Row(children: [
      Expanded(
        child: Semantics(
          button: true,
          label: 'Open $name',
          excludeSemantics: true,
          child: InkWell(
            borderRadius: BorderRadius.circular(KoloVibeRadii.tile),
            onTap: onOpen,
            child: ConstrainedBox(
              constraints: const BoxConstraints(minHeight: 48),
              child: Row(children: [
                KoloAvatar(name: name, size: 44),
                const SizedBox(width: 12),
                Expanded(
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                      Text(name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: KoloVibeText.body(16,
                              weight: FontWeight.w600,
                              color: KoloVibeColors.navy,
                              height: 1.3)),
                      if (detail.isNotEmpty)
                        Text(detail,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: KoloVibeText.body(12, height: 1.3)),
                    ])),
              ]),
            ),
          ),
        ),
      ),
      const SizedBox(width: 8),
      KoloPillButton(
        label: following == true ? 'Following' : 'Follow',
        selected: following == true,
        semanticLabel: '${following == true ? 'Unfollow' : 'Follow'} $name',
        onPressed: busy ? null : onFollow,
      ),
    ]);
  }
}

class _VideoRow extends StatelessWidget {
  const _VideoRow(
      {required this.kicker,
      required this.video,
      required this.meta,
      required this.onTap});
  final String kicker, meta;
  final LiveVideo video;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        label: '${video.title}. $meta',
        excludeSemantics: true,
        child: InkWell(
          borderRadius: BorderRadius.circular(KoloVibeRadii.tile),
          onTap: onTap,
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 60),
            child: Row(children: [
              ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: SizedBox(
                      width: 80,
                      height: 60,
                      child: _Poster(url: video.posterUrl, iconSize: 22))),
              const SizedBox(width: 12),
              Expanded(
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                    Text(kicker,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: KoloVibeText.body(10,
                            weight: FontWeight.w600,
                            color: KoloVibeColors.red,
                            height: 1.48,
                            letterSpacing: 0.4)),
                    Text(video.title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: KoloVibeText.body(13,
                            weight: FontWeight.w600,
                            color: KoloVibeColors.navy,
                            height: 1.35)),
                    if (meta.isNotEmpty)
                      Text(meta,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: KoloVibeText.body(11, height: 1.48)),
                  ])),
            ]),
          ),
        ),
      );
}
