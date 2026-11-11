import 'package:flutter/material.dart';
import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import '../../core/presentation/design_node.dart';
import '../account/live_account_repository.dart';
import '../creators/live_creator_repository.dart';
import '../system/system_ui.dart';
import 'live_video_repository.dart';

void discoveryNavigate(BuildContext context, int screen, [String? id]) {
  final route = ScreenRoute(screen, entityId: id);
  Navigator.of(context).pushNamed(route.name, arguments: route);
}

Widget videoTile(BuildContext context, LiveVideo video) => Card(
    child: ListTile(
        leading: video.posterUrl == null
            ? const Icon(Icons.movie_outlined)
            : Image.network(video.posterUrl.toString(),
                width: 64,
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => const Icon(Icons.movie_outlined)),
        title: Text(video.title),
        subtitle: Text(
            '${video.category ?? 'Original'} · ${video.likeCount == null ? 'Likes unavailable' : '${video.likeCount} likes'}'),
        onTap: () => discoveryNavigate(context, 25, video.id)));

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
  Object? error;
  final sections = <String, LiveVideoPage>{};
  final sectionErrors = <String, Object>{};
  int generation = 0;
  @override
  void initState() {
    super.initState();
    query = widget.initialQuery;
    category = widget.initialCategory;
    search.text = query ?? '';
    searched = query != null;
    if (widget.screen != 21 && widget.screen != 23) load(reset: true);
  }

  @override
  void dispose() {
    generation++;
    searchFocus.dispose();
    search.clear();
    search.dispose();
    super.dispose();
  }

  Future<void> home() async {
    await Future.wait(['Following', 'Trending', 'Latest'].map((name) async {
      try {
        final page = name == 'Following'
            ? widget.account == null
                ? throw const ApiFailure(401, 'Sign in')
                : await widget.repository.followingPage(widget.account!)
            : await widget.repository
                .filteredPage(sort: name == 'Trending' ? 'trending' : 'recent');
        if (mounted) setState(() => sections[name] = page);
      } catch (failure) {
        if (mounted) setState(() => sectionErrors[name] = failure);
      }
    }));
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
        sections.clear();
        sectionErrors.clear();
      }
    });
    try {
      if (widget.screen == 17) {
        await home();
        return;
      }
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
                sort: widget.screen == 20 ? 'trending' : 'recent');
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
                    child: Padding(
                        padding: const EdgeInsets.all(24),
                        child:
                            Column(mainAxisSize: MainAxisSize.min, children: [
                          const Text('Find your kind of story'),
                          const Text('Filter video results by category.'),
                          Wrap(children: [
                            for (final value in <String?>[
                              null,
                              ...videoCategories
                            ])
                              ChoiceChip(
                                  label: Text(value?.replaceAll('_', ' ') ??
                                      'All categories'),
                                  selected: selected == value,
                                  onSelected: (_) =>
                                      update(() => selected = value))
                          ]),
                          FilledButton(
                              onPressed: () =>
                                  Navigator.pop(sheet, (category: selected)),
                              child: const Text('Apply category')),
                          TextButton(
                              onPressed: () => update(() => selected = null),
                              child: const Text('Reset filters')),
                        ]))))));
    if (!mounted || result == null) return;
    setState(() => category = result.category);
    await load(reset: true);
  }

  Widget failure(Object value, VoidCallback retry) => SystemFailureView(
      error: value,
      onRetry: retry,
      onSignIn: () => discoveryNavigate(context, 4));
  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(
          title: Text(widget.screen == 27
              ? 'Published videos'
              : widget.catalog[widget.screen].name),
          actions: [
            if (widget.screen == 17)
              IconButton(
                  tooltip: 'Search',
                  onPressed: () => discoveryNavigate(context, 21),
                  icon: const Icon(Icons.search)),
            if ({19, 21, 22, 23}.contains(widget.screen))
              TextButton(
                  onPressed: busy ? null : filters,
                  child: const Text('Filters')),
          ]),
      body: SafeArea(
          child: Column(children: [
        if ({19, 21, 22, 23}.contains(widget.screen))
          Padding(
              padding: const EdgeInsets.all(16),
              child: TextField(
                  controller: search,
                  focusNode: searchFocus,
                  maxLength: 100,
                  enabled: !busy,
                  textInputAction: TextInputAction.search,
                  decoration: const InputDecoration(
                      labelText: 'Search videos and creators'),
                  onSubmitted: (value) {
                    final term = value.trim();
                    if ({19, 21}.contains(widget.screen) && term.isNotEmpty) {
                      Navigator.of(context).push(MaterialPageRoute<void>(
                          settings:
                              RouteSettings(name: const ScreenRoute(22).name),
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
                  })),
        if (widget.screen == 19)
          SizedBox(
              height: 48,
              child: ListView(scrollDirection: Axis.horizontal, children: [
                for (final value in <String?>[null, ...videoCategories])
                  Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                      child: ChoiceChip(
                          label: Text(value?.replaceAll('_', ' ') ?? 'All'),
                          selected: category == value,
                          onSelected: busy
                              ? null
                              : (_) {
                                  category = value;
                                  load(reset: true);
                                }))
              ])),
        Expanded(
            child: widget.screen == 17
                ? ListView(padding: const EdgeInsets.all(16), children: [
                    for (final name in ['Following', 'Trending', 'Latest']) ...[
                      ListTile(
                          title: Text(name),
                          trailing: TextButton(
                              onPressed: () => discoveryNavigate(
                                  context,
                                  name == 'Following'
                                      ? 18
                                      : name == 'Trending'
                                          ? 20
                                          : 19),
                              child: const Text('View all'))),
                      if (sectionErrors[name] != null)
                        failure(sectionErrors[name]!, () => load(reset: true))
                      else if (sections[name] == null)
                        const SystemLoading()
                      else if (sections[name]!.items.isEmpty)
                        Text(
                            'No ${name.toLowerCase()} originals are available yet.')
                      else
                        ...sections[name]!
                            .items
                            .take(4)
                            .map((v) => videoTile(context, v)),
                    ]
                  ])
                : ListView(padding: const EdgeInsets.all(16), children: [
                    if (items.isNotEmpty) const Text('Videos'),
                    ...items.map((v) => videoTile(context, v)),
                    if (creatorItems.isNotEmpty) const Text('Creators'),
                    for (final creator in creatorItems)
                      ListTile(
                          title: Text(creator.displayName.isEmpty
                              ? '@${creator.handle}'
                              : creator.displayName),
                          subtitle:
                              Text('@${creator.handle} · ${creator.location}'),
                          onTap: () =>
                              discoveryNavigate(context, 26, creator.id)),
                    if (busy) const SystemLoading(),
                    if (error != null)
                      failure(
                          error!,
                          () => load(
                              reset: items.isEmpty && !retryCreators,
                              creatorsOnly: retryCreators)),
                    if (!busy &&
                        error == null &&
                        items.isEmpty &&
                        creatorItems.isEmpty)
                      searched
                          ? SystemEmpty(
                              query: query ?? '',
                              onEdit: () => searchFocus.requestFocus())
                          : Text(widget.screen == 18
                              ? 'Follow creators to see their originals here.'
                              : 'No originals are available yet.'),
                    if (!busy && cursor != null)
                      OutlinedButton(
                          onPressed: load,
                          child: const Text('Load more videos')),
                    if (!busy && creatorCursor != null)
                      OutlinedButton(
                          onPressed: () => load(creatorsOnly: true),
                          child: const Text('Load more creators')),
                    if (!busy && widget.screen == 23)
                      FilledButton(
                          onPressed: filters,
                          child: const Text('Choose category')),
                  ])),
      ])));
}
