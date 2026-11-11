import 'package:flutter/material.dart';

import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import 'live_points_repository.dart';

class LivePointsScreen extends StatefulWidget {
  const LivePointsScreen(
      {super.key, required this.route, required this.repository});
  final ScreenRoute route;
  final LivePointsRepository repository;

  @override
  State<LivePointsScreen> createState() => _LivePointsScreenState();
}

class _LivePointsScreenState extends State<LivePointsScreen> {
  PointsBalance? balance;
  final entries = <PointsEntry>[];
  String? cursor;
  String? error;
  bool loading = true;
  bool loadingMore = false;

  @override
  void initState() {
    super.initState();
    reload();
  }

  Future<void> reload() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final current = await widget.repository.balance();
      final page = await widget.repository.entries();
      if (page.items.any((item) => item.creatorId != current.creatorId)) {
        throw const FormatException('Mismatched points owner');
      }
      if (!mounted) return;
      setState(() {
        balance = current;
        entries
          ..clear()
          ..addAll(page.items);
        cursor = page.nextCursor;
      });
    } on ApiFailure catch (failure) {
      if (mounted) setState(() => error = failure.message);
    } on FormatException {
      if (mounted) setState(() => error = 'Points data could not be read.');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> loadMore() async {
    if (loadingMore || cursor == null) return;
    setState(() {
      loadingMore = true;
      error = null;
    });
    try {
      final page = await widget.repository.entries(cursor: cursor);
      final known = entries.map((item) => item.id).toSet();
      if (page.items.any((item) =>
          item.creatorId != balance?.creatorId || known.contains(item.id))) {
        throw const FormatException('Invalid points page');
      }
      if (!mounted) return;
      setState(() {
        entries.addAll(page.items);
        cursor = page.nextCursor;
      });
    } on ApiFailure catch (failure) {
      if (mounted) setState(() => error = failure.message);
    } on FormatException {
      if (mounted) setState(() => error = 'Points data could not be read.');
    } finally {
      if (mounted) setState(() => loadingMore = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final selected = widget.route.screen;
    final shown = entries
        .where((entry) => switch (selected) {
              62 => entry.kind == 'award',
              63 => false,
              66 => false,
              67 => entry.kind == 'reversal',
              _ => true,
            })
        .toList();
    return Scaffold(
      appBar: AppBar(title: const Text('Lone Stars')),
      body: SafeArea(child: Builder(builder: (context) {
        if (loading && balance == null) {
          return const Center(child: CircularProgressIndicator());
        }
        if (balance == null) {
          return Center(
              child: Column(mainAxisSize: MainAxisSize.min, children: [
            Text(error ?? 'Points are unavailable.'),
            TextButton(onPressed: reload, child: const Text('Try again')),
          ]));
        }
        return RefreshIndicator(
          onRefresh: reload,
          child: ListView(padding: const EdgeInsets.all(20), children: [
            Text('Confirmed Lone Stars',
                style: Theme.of(context).textTheme.titleMedium),
            Text('${balance!.balance}',
                style: Theme.of(context).textTheme.displayMedium),
            const Text('Non-cash points'),
            const SizedBox(height: 24),
            const Text('Activity'),
            if (shown.isEmpty)
              const ListTile(title: Text('No points activity yet.')),
            for (final entry in shown)
              ListTile(
                title:
                    Text(entry.kind == 'award' ? 'Qualified view' : entry.kind),
                subtitle: Text(MaterialLocalizations.of(context)
                    .formatMediumDate(entry.createdAt.toLocal())),
                trailing: Text('${entry.amount > 0 ? '+' : ''}${entry.amount}'),
              ),
            if (error != null) Semantics(liveRegion: true, child: Text(error!)),
            if (loadingMore) const Center(child: CircularProgressIndicator()),
            if (!loadingMore && (cursor != null || error != null))
              TextButton(
                  onPressed: cursor == null ? reload : loadMore,
                  child: const Text('Load more')),
          ]),
        );
      })),
    );
  }
}
