import 'package:flutter/material.dart';

import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import 'live_creator_repository.dart';

class CreatorSearchScreen extends StatefulWidget {
  const CreatorSearchScreen({super.key, required this.repository});

  final LiveCreatorRepository repository;

  @override
  State<CreatorSearchScreen> createState() => _CreatorSearchScreenState();
}

class _CreatorSearchScreenState extends State<CreatorSearchScreen> {
  final _items = <LiveCreator>[];
  String? _query;
  String? _cursor;
  String? _error;
  bool _loading = false;

  Future<void> _load({String? query}) async {
    if (_loading) return;
    if (query != null && query.trim().isEmpty) return;
    setState(() {
      if (query != null) {
        _query = query.trim();
        _items.clear();
        _cursor = null;
      }
      _loading = true;
      _error = null;
    });
    try {
      final page = await widget.repository.search(_query!, cursor: _cursor);
      if (!mounted) return;
      final seen = _items.map((item) => item.id).toSet();
      if (page.items.any((item) => seen.contains(item.id))) {
        throw const FormatException('Repeated creator search page');
      }
      setState(() {
        _items.addAll(page.items);
        _cursor = page.nextCursor;
      });
    } on ApiFailure catch (failure) {
      if (mounted) setState(() => _error = failure.message);
    } on FormatException {
      if (mounted) setState(() => _error = 'Invalid search response.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Find creators')),
    body: SafeArea(
      child: Column(children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: TextField(
            enabled: !_loading,
            maxLength: 100,
            textInputAction: TextInputAction.search,
            decoration: const InputDecoration(labelText: 'Search by handle'),
            onSubmitted: (query) => _load(query: query),
          ),
        ),
        Expanded(
          child: ListView(
            children: [
              for (final creator in _items)
                ListTile(
                  title: Text('@${creator.handle}'),
                  subtitle: creator.bio.isEmpty ? null : Text(creator.bio),
                  onTap: () {
                    final route = ScreenRoute(38, entityId: creator.id);
                    Navigator.of(context).pushNamed(route.name, arguments: route);
                  },
                ),
              if (_loading) const Center(child: CircularProgressIndicator()),
              if (!_loading && _error != null)
                Semantics(liveRegion: true, child: Text(_error!)),
              if (!_loading && _error == null && _query != null && _items.isEmpty)
                const Center(child: Text('No creators match your search.')),
              if (!_loading && (_cursor != null || _error != null))
                TextButton(
                  onPressed: _load,
                  child: Text(_error == null ? 'Load more' : 'Try again'),
                ),
            ],
          ),
        ),
      ]),
    ),
  );
}
