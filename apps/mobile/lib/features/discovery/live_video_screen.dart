import 'package:flutter/material.dart';
import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import '../../core/presentation/design_node.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../shell/main_shell.dart';
import 'live_video_repository.dart';

class LiveVideoScreen extends StatefulWidget {
  const LiveVideoScreen(
      {super.key,
      required this.route,
      required this.catalog,
      required this.repository});
  final ScreenRoute route;
  final DesignCatalog catalog;
  final LiveVideoRepository repository;

  @override
  State<LiveVideoScreen> createState() => _LiveVideoScreenState();
}

class _LiveVideoScreenState extends State<LiveVideoScreen> {
  List<LiveVideo>? videos;
  String? nextCursor;
  String? error;
  bool loading = false;

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
      final page =
          await widget.repository.page(cursor: reset ? null : nextCursor);
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
            title: Text(widget.route.screen == 17
                ? 'KoloVibe'
                : widget.route.screen == 24
                    ? 'Videos'
                    : 'Explore')),
        body: SafeArea(child: Builder(
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
              return _state(context, error ?? 'No originals are available yet.',
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
        bottomNavigationBar: MainShell(
          navigation:
              widget.catalog[widget.route.screen].named('Primary navigation')!,
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
      {super.key, required this.id, required this.repository});
  final String id;
  final LiveVideoRepository repository;

  @override
  State<LiveVideoDetailScreen> createState() => _LiveVideoDetailScreenState();
}

class _LiveVideoDetailScreenState extends State<LiveVideoDetailScreen> {
  LiveVideo? item;
  Object? error;
  bool loading = true;

  @override
  void initState() {
    super.initState();
    load();
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
              const SizedBox(height: 16),
              TextButton(
                  onPressed: () {
                    final route = ScreenRoute(38, entityId: video.creatorId);
                    Navigator.of(context)
                        .pushNamed(route.name, arguments: route);
                  },
                  child: const Text('View creator')),
              const SizedBox(height: 24),
              const Text(
                  'Playback is awaiting an approved streaming provider.'),
            ]);
          },
        )),
      );
}
