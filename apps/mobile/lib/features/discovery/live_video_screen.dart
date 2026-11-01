import 'package:flutter/material.dart';
import '../../app/screen_route.dart';
import '../../core/presentation/design_node.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../shell/main_shell.dart';
import 'live_video_repository.dart';

class LiveVideoScreen extends StatefulWidget {
  const LiveVideoScreen({super.key, required this.route, required this.catalog,
    required this.repository});
  final ScreenRoute route;
  final DesignCatalog catalog;
  final LiveVideoRepository repository;

  @override
  State<LiveVideoScreen> createState() => _LiveVideoScreenState();
}

class _LiveVideoScreenState extends State<LiveVideoScreen> {
  late Future<List<LiveVideo>> videos;

  @override
  void initState() {
    super.initState();
    videos = widget.repository.list();
  }

  void reload() => setState(() => videos = widget.repository.list());

  void navigate(int screen, {String? entityId}) {
    final route = ScreenRoute(screen, entityId: entityId);
    Navigator.of(context).pushReplacementNamed(route.name, arguments: route);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(widget.route.screen == 17 ? 'KoloVibe' :
        widget.route.screen == 24 ? 'Videos' : 'Explore')),
    body: SafeArea(child: FutureBuilder<List<LiveVideo>>(
      future: videos,
      builder: (context, snapshot) {
        if (!snapshot.hasData && !snapshot.hasError) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return _state(context, 'Videos are temporarily unavailable.', onRetry: reload);
        }
        final items = snapshot.data!;
        if (items.isEmpty) return _state(context, 'No originals are available yet.', onRetry: reload);
        return RefreshIndicator(
          onRefresh: () async { reload(); await videos; },
          child: ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: items.length,
            separatorBuilder: (_, __) => const SizedBox(height: 12),
            itemBuilder: (context, index) {
              final video = items[index];
              return Card(child: ListTile(
                title: Text(video.title),
                subtitle: video.description.isEmpty ? null : Text(video.description),
                trailing: const Icon(Icons.chevron_right),
                onTap: () {
                  final route = ScreenRoute(25, entityId: video.id);
                  Navigator.of(context).pushNamed(route.name, arguments: route);
                },
              ));
            },
          ),
        );
      },
    )),
    bottomNavigationBar: MainShell(
      navigation: widget.catalog[widget.route.screen].named('Primary navigation')!,
      screen: widget.route.screen, onSelected: navigate,
    ),
  );

  Widget _state(BuildContext context, String message, {required VoidCallback onRetry}) =>
      Center(child: Padding(padding: const EdgeInsets.all(24), child: Column(
        mainAxisSize: MainAxisSize.min, children: [
          const Icon(Icons.video_library_outlined, size: 48, color: KoloVibeColors.navy),
          const SizedBox(height: 16), Text(message, textAlign: TextAlign.center),
          const SizedBox(height: 16), OutlinedButton(onPressed: onRetry, child: const Text('Try again')),
        ],
      )));
}

class LiveVideoDetailScreen extends StatelessWidget {
  const LiveVideoDetailScreen({super.key, required this.id, required this.repository});
  final String id;
  final LiveVideoRepository repository;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Original')),
    body: SafeArea(child: FutureBuilder<LiveVideo>(
      future: repository.detail(id),
      builder: (context, snapshot) {
        if (!snapshot.hasData && !snapshot.hasError) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return const Center(child: Text('This original is unavailable.'));
        }
        final video = snapshot.data!;
        return ListView(padding: const EdgeInsets.all(24), children: [
          Text(video.title, style: Theme.of(context).textTheme.headlineMedium),
          const SizedBox(height: 16), Text(video.description),
          const SizedBox(height: 16),
          TextButton(onPressed: () {
            final route = ScreenRoute(38, entityId: video.creatorId);
            Navigator.of(context).pushNamed(route.name, arguments: route);
          }, child: const Text('View creator')),
          const SizedBox(height: 24),
          const Text('Playback is awaiting an approved streaming provider.'),
        ]);
      },
    )),
  );
}
