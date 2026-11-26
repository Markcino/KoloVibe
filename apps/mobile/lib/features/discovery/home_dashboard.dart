import 'package:flutter/material.dart';
import '../../core/network/api_client.dart';
import '../../core/presentation/design_node.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/kolo_components.dart';
import '../../shared/widgets/kolo_media.dart';
import '../account/live_account_repository.dart';
import '../creators/live_creator_repository.dart';
import '../shell/main_shell.dart';
import '../engagement/like_counts.dart';
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
    this.selectTab,
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

  /// Bottom-navigation tab selection; defaults to [navigate].
  final ValueChanged<int>? selectTab;
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
    LikeCounts.shared.addListener(_likesChanged);
    load();
  }

  void _likesChanged() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    generation++;
    LikeCounts.shared.removeListener(_likesChanged);
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
        if (likes)
          if (LikeCounts.shared.current(video.id, video.likeCount)
              case final count?)
            _likes(count),
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
                          // SIM-01: an emoji renders as missing glyphs on
                          // some devices, so the sun is the icon the design
                          // export uses (see design_view.dart).
                          child: Text.rich(
                              TextSpan(text: greeting, children: [
                                if (morning) ...[
                                  const TextSpan(text: ' '),
                                  const WidgetSpan(
                                      alignment: PlaceholderAlignment.middle,
                                      child: ExcludeSemantics(
                                          child: Icon(Icons.wb_sunny_rounded,
                                              color: Color(0xffffba24),
                                              size: 25))),
                                ],
                              ]),
                              semanticsLabel: greeting,
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
        onSelected: (target) => (widget.selectTab ?? widget.navigate)(target),
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
          message:
              'Originals trend here once people watch and like them. Explore has everything published.',
          icon: Icons.local_fire_department_outlined);
    }
    final video = trending.first;
    final meta = _meta(video);
    return KoloHeroCard(
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
            message:
                'Creators appear here once their originals start trending.',
            icon: Icons.people_outline)
      ];
    }
    return [
      for (final creator in shown) ...[
        KoloCreatorRow(
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
      KoloVideoRow(
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
        KoloVideoRow(
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
