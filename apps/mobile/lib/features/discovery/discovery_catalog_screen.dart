import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import '../../core/presentation/design_node.dart';
import '../account/live_account_repository.dart';
import '../creators/live_creator_repository.dart';
import '../system/system_ui.dart';
import 'home_dashboard.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/kolo_components.dart';
import '../../shared/widgets/kolo_media.dart';
import '../shell/main_shell.dart';
import 'live_video_repository.dart';

void discoveryNavigate(BuildContext context, int screen, [String? id]) {
  final route = ScreenRoute(screen, entityId: id);
  Navigator.of(context).pushNamed(route.name, arguments: route);
}

String videoMeta(LiveVideo video) => [
      if (video.category != null) categoryLabel(video.category!),
      if (formatDuration(video.durationMs) != null)
        formatDuration(video.durationMs)!,
      if (video.likeCount != null)
        '${video.likeCount} ${video.likeCount == 1 ? 'like' : 'likes'}',
    ].join(' · ');

Widget videoTile(BuildContext context, LiveVideo video) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: KoloVideoRow(
        video: video,
        meta: videoMeta(video),
        onTap: () => discoveryNavigate(context, 25, video.id)));

/// Bottom-navigation tabs replace the current tab, so Back never walks
/// through every tab that was visited.
void discoveryTab(BuildContext context, int screen) {
  final route = ScreenRoute(screen);
  Navigator.of(context).pushReplacementNamed(route.name, arguments: route);
}

class DiscoveryCatalogScreen extends StatefulWidget {
  const DiscoveryCatalogScreen(
      {super.key,
      required this.screen,
      required this.repository,
      required this.catalog,
      this.account,
      this.creators,
      this.creatorId,
      this.initialQuery,
      this.initialCategory});
  final int screen;
  final LiveVideoRepository repository;
  final DesignCatalog catalog;
  final LiveAccountRepository? account;
  final LiveCreatorRepository? creators;
  final String? creatorId;
  final String? initialQuery, initialCategory;
  @override
  State<DiscoveryCatalogScreen> createState() => _DiscoveryCatalogState();
}

class _DiscoveryCatalogState extends State<DiscoveryCatalogScreen> {
  final search = TextEditingController();
  final searchFocus = FocusNode();
  final items = <LiveVideo>[];
  final creatorItems = <LiveCreator>[];
  String? cursor, creatorCursor, category, query;
  bool busy = false, searched = false, retryCreators = false;
  // M-020: false = Trending, true = Fresh picks. M-027: false = Latest, true =
  // Trending. M-022: 0 all results, 1 videos, 2 creators.
  bool alternate = false;
  int resultFilter = 0;
  LiveCreator? spotlight, profile;
  Object? error;
  int generation = 0;
  @override
  void initState() {
    super.initState();
    query = widget.initialQuery;
    category = widget.initialCategory;
    search.text = query ?? '';
    searched = query != null;
    if (!{17, 21, 23}.contains(widget.screen)) load(reset: true);
    if (widget.screen == 27 &&
        widget.creatorId != null &&
        widget.creators != null) {
      _loadProfile();
    }
  }

  Future<void> _loadProfile() async {
    try {
      final value = await widget.creators!.detail(widget.creatorId!);
      if (mounted) setState(() => profile = value);
    } catch (_) {
      // The header is optional; the list stays usable without it.
    }
  }

  /// The creator of the first result, shown as the spotlight on Explore.
  Future<void> _loadSpotlight() async {
    if (widget.screen != 19 || widget.creators == null || items.isEmpty) return;
    final creatorId = items.first.creatorId;
    if (spotlight?.id == creatorId) return;
    try {
      final value = await widget.creators!.detail(creatorId);
      if (mounted && items.isNotEmpty && items.first.creatorId == creatorId) {
        setState(() => spotlight = value);
      }
    } catch (_) {
      if (mounted) setState(() => spotlight = null);
    }
  }

  @override
  void dispose() {
    generation++;
    searchFocus.dispose();
    search.clear();
    search.dispose();
    super.dispose();
  }

  Future<void> load({bool reset = false, bool creatorsOnly = false}) async {
    if (busy) return;
    final token = ++generation;
    setState(() {
      busy = true;
      error = null;
      if (reset) {
        items.clear();
        creatorItems.clear();
        cursor = null;
        creatorCursor = null;
      }
    });
    try {
      if (!creatorsOnly) {
        final page = widget.screen == 18
            ? widget.account == null
                ? throw const ApiFailure(401, 'Sign in')
                : await widget.repository
                    .followingPage(widget.account!, cursor: cursor)
            : await widget.repository.filteredPage(
                cursor: cursor,
                creatorId: widget.creatorId,
                query: query,
                category: category,
                sort: switch (widget.screen) {
                  20 => alternate ? 'recent' : 'trending',
                  27 => alternate ? 'trending' : 'recent',
                  _ => 'recent',
                });
        if (!mounted || token != generation) return;
        final seen = items.map((e) => e.id).toSet();
        if (page.items.any((e) => seen.contains(e.id))) {
          throw const FormatException('Repeated page');
        }
        items.addAll(page.items);
        cursor = page.nextCursor;
      }
      if (query != null && widget.creators != null && (reset || creatorsOnly)) {
        retryCreators = true;
        final result =
            await widget.creators!.search(query!, cursor: creatorCursor);
        if (!mounted || token != generation) return;
        final seen = creatorItems.map((e) => e.id).toSet();
        if (result.items.any((e) => seen.contains(e.id))) {
          throw const FormatException('Repeated creators');
        }
        creatorItems.addAll(result.items);
        creatorCursor = result.nextCursor;
        retryCreators = false;
      }
    } catch (failure) {
      if (mounted && token == generation) error = failure;
    } finally {
      if (mounted && token == generation) setState(() => busy = false);
    }
    if (mounted && token == generation && error == null) _loadSpotlight();
  }

  Future<void> filters() async {
    var selected = category;
    final result = await showModalBottomSheet<({String? category})>(
        context: context,
        routeSettings: RouteSettings(name: const ScreenRoute(23).name),
        isScrollControlled: true,
        builder: (sheet) => StatefulBuilder(
            builder: (context, update) => SafeArea(
                child: SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
                    child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          const KoloHeadline('Find your kind of story',
                              size: 24),
                          const SizedBox(height: 8),
                          Text('Filter video results by category.',
                              style: KoloVibeText.body(14, height: 1.45)),
                          const SizedBox(height: 16),
                          Wrap(spacing: 8, runSpacing: 8, children: [
                            for (final value in <String?>[
                              null,
                              ...videoCategories
                            ])
                              ChoiceChip(
                                  label: Text(value == null
                                      ? 'All categories'
                                      : categoryLabel(value)),
                                  labelStyle: KoloVibeText.body(12,
                                      weight: FontWeight.w600,
                                      color: selected == value
                                          ? Colors.white
                                          : KoloVibeColors.navy),
                                  selected: selected == value,
                                  onSelected: (_) =>
                                      update(() => selected = value))
                          ]),
                          const SizedBox(height: 24),
                          FilledButton(
                              onPressed: () =>
                                  Navigator.pop(sheet, (category: selected)),
                              child: const Text('Apply category')),
                          const SizedBox(height: 12),
                          OutlinedButton(
                              onPressed: () => update(() => selected = null),
                              child: const Text('Reset filters')),
                        ])))));
    if (!mounted || result == null) return;
    setState(() => category = result.category);
    await load(reset: true);
  }

  Widget failure(Object value, VoidCallback retry) => SystemFailureView(
      error: value,
      onRetry: retry,
      onSignIn: () => discoveryNavigate(context, 4));
  void openCategory(String slug) =>
      Navigator.of(context).push(MaterialPageRoute<void>(
          settings: RouteSettings(name: const ScreenRoute(19).name),
          builder: (_) => DiscoveryCatalogScreen(
              screen: 19,
              repository: widget.repository,
              catalog: widget.catalog,
              account: widget.account,
              creators: widget.creators,
              initialCategory: slug)));

  @override
  Widget build(BuildContext context) => widget.screen == 17
      ? HomeDashboard(
          videos: widget.repository,
          creators: widget.creators,
          account: widget.account,
          catalog: widget.catalog,
          navigate: (screen, [id]) => discoveryNavigate(context, screen, id),
          selectTab: (screen) => discoveryTab(context, screen),
          openCategory: openCategory)
      : _catalogScaffold(context);

  Widget _search(BuildContext context) => Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextField(
          controller: search,
          focusNode: searchFocus,
          maxLength: 100,
          enabled: !busy,
          textInputAction: TextInputAction.search,
          style: KoloVibeText.body(14, color: KoloVibeColors.ink),
          decoration: InputDecoration(
              hintText: 'Search KoloVibe',
              counterText: '',
              prefixIcon: Padding(
                  padding: const EdgeInsets.all(14),
                  child: SvgPicture.asset(
                      'assets/images/96a2f99af25ad7f6acca.svg',
                      width: 20,
                      height: 20,
                      excludeFromSemantics: true)),
              suffixIcon: IconButton(
                  tooltip: 'Filters',
                  onPressed: busy ? null : filters,
                  icon: SvgPicture.asset(
                      'assets/images/84754de6e461aa4a37de.svg',
                      width: 18,
                      height: 18,
                      excludeFromSemantics: true))),
          onSubmitted: (value) {
            final term = value.trim();
            if ({19, 21}.contains(widget.screen) && term.isNotEmpty) {
              Navigator.of(context).push(MaterialPageRoute<void>(
                  settings: RouteSettings(name: const ScreenRoute(22).name),
                  builder: (_) => DiscoveryCatalogScreen(
                      screen: 22,
                      repository: widget.repository,
                      catalog: widget.catalog,
                      account: widget.account,
                      creators: widget.creators,
                      initialQuery: term,
                      initialCategory: category)));
            } else {
              query = term.isEmpty ? null : term;
              searched = query != null;
              load(reset: true);
            }
          }));

  Widget _chipRow(List<(String, bool, VoidCallback?)> chips) =>
      Wrap(spacing: 8, runSpacing: 4, children: [
        for (final (label, selected, onTap) in chips)
          ChoiceChip(
              label: Text(label),
              labelStyle: KoloVibeText.body(12,
                  weight: FontWeight.w600,
                  color: selected ? Colors.white : KoloVibeColors.navy),
              selected: selected,
              onSelected: onTap == null ? null : (_) => onTap()),
      ]);

  List<Widget> _categoryChips() => [
        _chipRow([
          for (final value in <String?>[null, ...videoCategories])
            (
              value == null ? 'All' : categoryLabel(value),
              category == value,
              busy
                  ? null
                  : () {
                      category = value;
                      load(reset: true);
                    }
            )
        ]),
        const SizedBox(height: 12),
      ];

  Widget _grid(List<LiveVideo> videos, {double posterHeight = 92}) =>
      Column(children: [
        for (var i = 0; i < videos.length; i += 2)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Expanded(
                  child: KoloVideoCard(
                      video: videos[i],
                      meta: videoMeta(videos[i]),
                      posterHeight: posterHeight,
                      titleSize: posterHeight > 100 ? 13 : 12,
                      onTap: () =>
                          discoveryNavigate(context, 25, videos[i].id))),
              const SizedBox(width: 12),
              Expanded(
                  child: i + 1 < videos.length
                      ? KoloVideoCard(
                          video: videos[i + 1],
                          meta: videoMeta(videos[i + 1]),
                          posterHeight: posterHeight,
                          titleSize: posterHeight > 100 ? 13 : 12,
                          onTap: () =>
                              discoveryNavigate(context, 25, videos[i + 1].id))
                      : const SizedBox()),
            ]),
          ),
      ]);

  Widget _creatorRow(LiveCreator creator,
          {String? actionLabel, bool bio = false}) =>
      Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: KoloCreatorRow(
              creator: creator,
              showBio: bio,
              actionLabel: actionLabel,
              onFollow: actionLabel == null
                  ? null
                  : () => discoveryNavigate(context, 26, creator.id),
              onOpen: () => discoveryNavigate(context, 26, creator.id)));

  /// Explore (M-019): the latest originals from the service. The hero is the
  /// newest original, "Fresh perspectives" the next two and the creator
  /// spotlight its creator. Nothing is curated by hand: the design's
  /// "Curated collection" label is replaced by "Latest original".
  List<Widget> _exploreSections() {
    if (items.isEmpty) return const [];
    final hero = items.first;
    final fresh = items.skip(1).take(2).toList();
    final rest = items.skip(3).toList();
    return [
      KoloHeroCard(
          video: hero,
          eyebrow: hero.category == null
              ? 'LATEST ORIGINAL'
              : 'LATEST ORIGINAL · ${categoryLabel(hero.category!).toUpperCase()}',
          minHeight: 144,
          meta: videoMeta(hero),
          onTap: () => discoveryNavigate(context, 25, hero.id)),
      if (fresh.isNotEmpty) ...[
        const SizedBox(height: 16),
        KoloSectionHeading(
            title: 'Fresh perspectives',
            actionLabel: 'View all',
            onAction: () => discoveryNavigate(context, 20)),
        const SizedBox(height: 12),
        _grid(fresh),
      ],
      if (spotlight != null) ...[
        const SizedBox(height: 4),
        Text('CREATOR SPOTLIGHT',
            style: KoloVibeText.body(11,
                weight: FontWeight.w600,
                color: KoloVibeColors.red,
                letterSpacing: 0.4)),
        const SizedBox(height: 12),
        _creatorRow(spotlight!, actionLabel: 'View'),
      ],
      if (rest.isNotEmpty) ...[
        const SizedBox(height: 8),
        const KoloSectionHeading(title: 'More originals'),
        const SizedBox(height: 12),
        ...rest.map((v) => videoTile(context, v)),
      ],
    ];
  }

  Widget _body(BuildContext context) {
    final searchy = {19, 21, 22, 23}.contains(widget.screen);
    final showVideos = widget.screen != 22 || resultFilter != 2;
    final showCreators = widget.screen != 22 || resultFilter != 1;
    return ListView(
        padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
        keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
        children: [
          if (widget.screen == 20) ...[
            Text('WHAT’S MOVING THE COMMUNITY',
                style: KoloVibeText.body(11,
                    weight: FontWeight.w600,
                    color: KoloVibeColors.red,
                    letterSpacing: 0.4)),
            const SizedBox(height: 8),
            const KoloHeadline('Big stories.\nLocal energy.', size: 32),
            const SizedBox(height: 16),
            _chipRow([
              ('Trending', !alternate, busy ? null : () => _switch(false)),
              ('Fresh picks', alternate, busy ? null : () => _switch(true)),
            ]),
            const SizedBox(height: 16),
          ],
          if (widget.screen == 27) ...[
            if (profile != null)
              _creatorRow(profile!, actionLabel: 'Profile')
            else
              const SizedBox(height: 4),
            _chipRow([
              ('Latest', !alternate, busy ? null : () => _switch(false)),
              ('Trending', alternate, busy ? null : () => _switch(true)),
            ]),
            const SizedBox(height: 12),
            if (profile?.publishedVideoCount != null)
              Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Text(
                      '${profile!.publishedVideoCount} published ${profile!.publishedVideoCount == 1 ? 'original' : 'originals'}',
                      style: KoloVibeText.body(12))),
          ],
          if (searchy) _search(context),
          if (widget.screen == 19) ...[
            ..._categoryChips(),
            ..._exploreSections(),
          ],
          if (widget.screen == 22 &&
              (items.isNotEmpty || creatorItems.isNotEmpty)) ...[
            _chipRow([
              (
                'All results',
                resultFilter == 0,
                () => setState(() => resultFilter = 0)
              ),
              (
                'Videos',
                resultFilter == 1,
                () => setState(() => resultFilter = 1)
              ),
              (
                'Creators',
                resultFilter == 2,
                () => setState(() => resultFilter = 2)
              ),
            ]),
            const SizedBox(height: 12),
            if (query != null)
              Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Text('Results for “$query”',
                      style: KoloVibeText.body(12))),
          ],
          if (items.isNotEmpty && widget.screen == 22 && showVideos)
            KoloSectionHeading(
                title: 'Videos',
                actionLabel: busy ? null : 'Filters',
                onAction: filters),
          if (items.isNotEmpty && widget.screen == 22 && showVideos)
            const SizedBox(height: 12),
          if (widget.screen == 20 && items.isNotEmpty) ...[
            KoloHeroCard(
                video: items.first,
                eyebrow: alternate ? 'FRESH PICK' : 'TRENDING ORIGINAL',
                meta: videoMeta(items.first),
                onTap: () => discoveryNavigate(context, 25, items.first.id)),
            const SizedBox(height: 16),
            ...items.skip(1).map((v) => videoTile(context, v)),
          ] else if (widget.screen == 27) ...[
            _grid(items, posterHeight: 135),
          ] else if (widget.screen != 19 && showVideos)
            ...items.map((v) => videoTile(context, v)),
          if (creatorItems.isNotEmpty && showCreators) ...[
            const SizedBox(height: 8),
            const KoloSectionHeading(title: 'Creators'),
            const SizedBox(height: 12),
            for (final creator in creatorItems)
              _creatorRow(creator, bio: widget.screen == 22),
          ],
          if (busy) const SystemLoading(),
          if (error != null)
            failure(
                error!,
                () => load(
                    reset: items.isEmpty && !retryCreators,
                    creatorsOnly: retryCreators)),
          // Search entry (M-021) and filters (M-023) have not asked the service
          // anything yet, so they show a hint, never an empty-catalogue claim.
          if (!busy &&
              !searched &&
              {21, 23}.contains(widget.screen) &&
              items.isEmpty &&
              creatorItems.isEmpty) ...[
            Padding(
                padding: const EdgeInsets.only(top: 8, bottom: 16),
                child: Text(
                    'Find original videos and the creators behind them.',
                    style: KoloVibeText.body(14, height: 1.5))),
            if (widget.screen == 21) ...[
              const KoloSectionHeading(title: 'Browse categories'),
              const SizedBox(height: 12),
              _chipRow([
                for (final value in videoCategories)
                  (categoryLabel(value), false, () => openCategory(value)),
              ]),
            ],
          ] else if (!busy &&
              error == null &&
              items.isEmpty &&
              creatorItems.isEmpty)
            searched
                ? SystemEmpty(
                    query: query ?? '',
                    onEdit: () => searchFocus.requestFocus())
                : KoloInlineState(
                    title: 'Nothing here yet',
                    message: widget.screen == 18
                        ? 'Follow creators to see their originals here.'
                        : 'No originals are available yet.',
                    icon: Icons.video_library_outlined),
          if (!busy && cursor != null)
            Padding(
                padding: const EdgeInsets.only(top: 8),
                child: OutlinedButton(
                    onPressed: load, child: const Text('Load more videos'))),
          if (!busy && creatorCursor != null)
            Padding(
                padding: const EdgeInsets.only(top: 8),
                child: OutlinedButton(
                    onPressed: () => load(creatorsOnly: true),
                    child: const Text('Load more creators'))),
          if (!busy && widget.screen == 23)
            Padding(
                padding: const EdgeInsets.only(top: 8),
                child: FilledButton(
                    onPressed: filters, child: const Text('Choose category'))),
        ]);
  }

  void _switch(bool value) {
    if (alternate == value) return;
    alternate = value;
    load(reset: true);
  }

  Widget _catalogScaffold(BuildContext context) {
    final navigation =
        widget.catalog[widget.screen].named('Primary navigation');
    return Scaffold(
      appBar: AppBar(
          title: Text(widget.screen == 27
              ? 'Published videos'
              : widget.catalog[widget.screen].name)),
      body: SafeArea(child: _body(context)),
      bottomNavigationBar: navigation == null
          ? null
          : MainShell(
              navigation: navigation,
              screen: widget.screen,
              onSelected: (target) => discoveryTab(context, target)),
    );
  }
}
