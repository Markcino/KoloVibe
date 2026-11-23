import 'package:flutter/material.dart';

import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import '../../core/presentation/design_node.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/kolo_media.dart';
import '../creators/creator_shell.dart';
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
  String _filter = 'all';
  String _query = '';
  final _search = TextEditingController();

  @override
  void initState() {
    super.initState();
    _load(reset: true);
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
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
      final page = await widget.repository.library(
          cursor: _cursor,
          state: _filter,
          query: _query.isEmpty ? null : _query);
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

  /// M-053; the library always re-reads afterwards, so publish, unpublish, edit and delete show at once.
  Future<void> _manage(OwnedVideo video) async {
    final route = ScreenRoute(53, entityId: video.id);
    await Navigator.of(context)
        .pushNamed<Object?>(route.name, arguments: route);
    if (mounted) await _load(reset: true);
  }

  void _notify(String message) => ScaffoldMessenger.of(context)
      .showSnackBar(SnackBar(content: Text(message)));

  Widget _row(OwnedVideo video) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(children: [
        InkWell(
            borderRadius: BorderRadius.circular(12),
            onTap: video.canEditDraft ? null : () => _manage(video),
            child: ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: SizedBox(
                    width: 80,
                    height: 60,
                    // A short-lived signed link: shown, never stored.
                    child: KoloPoster(
                        url: video.posterUrl == null
                            ? null
                            : Uri.tryParse(video.posterUrl!),
                        iconSize: 22)))),
        const SizedBox(width: 12),
        Expanded(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(video.title,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: KoloVibeText.body(14,
                  weight: FontWeight.w600, color: KoloVibeColors.navy)),
          const SizedBox(height: 2),
          Text(video.state,
              style: KoloVibeText.body(11,
                  weight: FontWeight.w600,
                  color: video.state == 'published'
                      ? KoloVibeColors.green
                      : video.state == 'rejected' || video.state == 'failed'
                          ? KoloVibeColors.red
                          : KoloVibeColors.muted)),
        ])),
        video.canEditDraft
            ? PopupMenuButton<String>(
                tooltip: 'Manage draft',
                onSelected: (action) {
                  if (action == 'edit') _edit(video);
                  if (action == 'delete') _delete(video);
                },
                itemBuilder: (_) => const [
                  PopupMenuItem(value: 'edit', child: Text('Edit draft')),
                  PopupMenuItem(value: 'delete', child: Text('Delete draft')),
                ],
              )
            : TextButton(
                onPressed: () => _manage(video), child: const Text('Manage')),
      ]));

  /// Runs the search the creator typed; blank input clears it. The service validates length and characters again.
  void _submitSearch(String value) {
    final text = value.trim();
    if (text == _query || _loading) return;
    if (text.length > 100 || text.runes.any((rune) => rune < 32)) {
      _notify('Search must be 1 to 100 characters.');
      return;
    }
    _query = text;
    _load(reset: true);
  }

  void _clearSearch() {
    _search.clear();
    if (_query.isEmpty) return;
    _query = '';
    _load(reset: true);
  }

  void _setFilter(String value) {
    if (_filter == value) return;
    _filter = value;
    _load(reset: true);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        bottomNavigationBar: creatorNavigation(context, widget.catalog, 40),
        appBar: AppBar(title: const Text('My video library')),
        body: SafeArea(
            child: RefreshIndicator(
          onRefresh: () => _load(reset: true),
          child: ListView(
              padding: const EdgeInsets.fromLTRB(24, 8, 24, 16),
              children: [
                TextField(
                  controller: _search,
                  textInputAction: TextInputAction.search,
                  maxLength: 100,
                  onSubmitted: _submitSearch,
                  decoration: InputDecoration(
                    labelText: 'Search my videos',
                    counterText: '',
                    prefixIcon: const Icon(Icons.search),
                    suffixIcon: IconButton(
                        tooltip: 'Clear search',
                        icon: const Icon(Icons.close),
                        onPressed: _clearSearch),
                  ),
                ),
                const SizedBox(height: 8),
                Wrap(spacing: 8, runSpacing: 4, children: [
                  for (final (label, value) in const [
                    ('All', 'all'),
                    ('Published', 'published'),
                    ('In progress', 'in_progress'),
                  ])
                    ChoiceChip(
                        label: Text(label),
                        labelStyle: KoloVibeText.body(12,
                            weight: FontWeight.w600,
                            color: _filter == value
                                ? Colors.white
                                : KoloVibeColors.navy),
                        selected: _filter == value,
                        onSelected: _loading ? null : (_) => _setFilter(value)),
                ]),
                const SizedBox(height: 8),
                if (_loading && !_loaded)
                  const Center(child: CircularProgressIndicator()),
                if (_error != null)
                  Padding(
                    padding: const EdgeInsets.all(16),
                    child: Semantics(liveRegion: true, child: Text(_error!)),
                  ),
                if (_loaded && _items.isEmpty && !_loading && _error == null)
                  Center(
                      child: Text(_query.isEmpty
                          ? 'You have no videos yet.'
                          : 'No videos match "$_query".')),
                for (final video in _items) _row(video),
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
