import 'package:flutter/material.dart';

import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import '../../core/presentation/design_node.dart';
import 'live_content_repository.dart';

class LiveContentScreen extends StatefulWidget {
  const LiveContentScreen(
      {super.key,
      required this.route,
      required this.catalog,
      required this.repository});

  final ScreenRoute route;
  final DesignCatalog catalog;
  final LiveContentRepository repository;

  @override
  State<LiveContentScreen> createState() => _LiveContentScreenState();
}

class _LiveContentScreenState extends State<LiveContentScreen> {
  final _items = <OwnedVideo>[];
  String? _cursor;
  String? _error;
  bool _loading = false;
  bool _loaded = false;

  @override
  void initState() {
    super.initState();
    _load(reset: true);
  }

  Future<void> _load({bool reset = false}) async {
    if (_loading) return;
    setState(() {
      _loading = true;
      _error = null;
      if (reset) {
        _items.clear();
        _cursor = null;
      }
    });
    try {
      final page = await widget.repository.library(cursor: _cursor);
      if (!mounted) return;
      final known = _items.map((video) => video.id).toSet();
      if (page.items.any((video) => known.contains(video.id))) {
        throw const FormatException('Repeated video page');
      }
      setState(() {
        _items.addAll(page.items);
        _cursor = page.nextCursor;
        _loaded = true;
      });
    } on ApiFailure catch (failure) {
      if (mounted) setState(() => _error = failure.message);
    } on FormatException {
      if (mounted) {
        setState(() => _error = 'The video library response was invalid.');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _edit(OwnedVideo video) async {
    var title = video.title;
    var description = video.description;
    final form = GlobalKey<FormState>();
    final changed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Edit draft'),
        content: Form(
          key: form,
          child: SingleChildScrollView(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              TextFormField(
                initialValue: title,
                maxLength: 160,
                decoration: const InputDecoration(labelText: 'Title'),
                onChanged: (value) => title = value,
                validator: (value) => value == null || value.trim().isEmpty
                    ? 'Enter a title'
                    : null,
              ),
              TextFormField(
                initialValue: description,
                maxLength: 2000,
                maxLines: 3,
                decoration: const InputDecoration(labelText: 'Description'),
                onChanged: (value) => description = value,
              ),
            ]),
          ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () {
                if (form.currentState?.validate() ?? false) {
                  Navigator.pop(context, true);
                }
              },
              child: const Text('Save')),
        ],
      ),
    );
    if (!mounted || changed != true) return;
    try {
      await widget.repository
          .editDraft(video, title: title, description: description);
      await _load(reset: true);
    } on ApiFailure catch (failure) {
      if (mounted) _notify(failure.message);
    } on FormatException {
      if (mounted) _notify('The draft could not be saved.');
    }
  }

  Future<void> _delete(OwnedVideo video) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete draft?'),
        content: const Text('This action cannot be undone.'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Delete')),
        ],
      ),
    );
    if (!mounted || confirmed != true) return;
    try {
      await widget.repository.deleteDraft(video);
      await _load(reset: true);
    } on ApiFailure catch (failure) {
      if (mounted) _notify(failure.message);
    } on FormatException {
      if (mounted) _notify('The draft could not be deleted.');
    }
  }

  void _notify(String message) => ScaffoldMessenger.of(context)
      .showSnackBar(SnackBar(content: Text(message)));

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('My video library')),
        body: SafeArea(
            child: RefreshIndicator(
          onRefresh: () => _load(reset: true),
          child: ListView(padding: const EdgeInsets.all(16), children: [
            if (_loading && !_loaded)
              const Center(child: CircularProgressIndicator()),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.all(16),
                child: Semantics(liveRegion: true, child: Text(_error!)),
              ),
            if (_loaded && _items.isEmpty && !_loading && _error == null)
              const Center(child: Text('You have no videos yet.')),
            for (final video in _items)
              Card(
                  child: ListTile(
                title: Text(video.title),
                subtitle: Text(video.state),
                trailing: video.canEditDraft
                    ? PopupMenuButton<String>(
                        tooltip: 'Manage draft',
                        onSelected: (action) {
                          if (action == 'edit') _edit(video);
                          if (action == 'delete') _delete(video);
                        },
                        itemBuilder: (_) => const [
                          PopupMenuItem(
                              value: 'edit', child: Text('Edit draft')),
                          PopupMenuItem(
                              value: 'delete', child: Text('Delete draft')),
                        ],
                      )
                    : null,
              )),
            if (_loading && _loaded)
              const Center(child: CircularProgressIndicator()),
            if (!_loading && (_cursor != null || _error != null))
              TextButton(
                  onPressed: () => _load(reset: _cursor == null),
                  child: Text(_error == null ? 'Load more' : 'Try again')),
          ]),
        )),
      );
}
