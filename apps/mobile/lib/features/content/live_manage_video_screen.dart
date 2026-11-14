import 'package:flutter/material.dart';
import '../../app/screen_route.dart';
import '../../shared/widgets/live_state_view.dart';
import '../creators/creator_shell.dart';
import 'live_content_repository.dart';
import 'manage_video_controller.dart';

/// M-053 Manage video with M-055 (unpublish) and M-056 (delete) confirmations and M-054 detail editing.
class LiveManageVideoScreen extends StatefulWidget {
  const LiveManageVideoScreen(
      {super.key,
      required this.videoId,
      required this.repository,
      this.controller});

  final String videoId;
  final LiveContentRepository repository;

  /// Test seam for a pre-built controller.
  final ManageVideoController? controller;

  @override
  State<LiveManageVideoScreen> createState() => _LiveManageVideoScreenState();
}

class _LiveManageVideoScreenState extends State<LiveManageVideoScreen> {
  late final ManageVideoController controller;

  @override
  void initState() {
    super.initState();
    controller = widget.controller ??
        ManageVideoController(widget.repository, widget.videoId);
    controller.addListener(_closeWhenDeleted);
    controller.load();
  }

  @override
  void dispose() {
    controller.removeListener(_closeWhenDeleted);
    controller.dispose();
    super.dispose();
  }

  void _closeWhenDeleted() {
    if (controller.deleted && mounted) Navigator.of(context).pop(true);
  }

  Future<bool> _confirm(String title, String body, String action,
      {bool destructive = false}) async {
    final result = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: Text(body),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          FilledButton(
              style: destructive
                  ? FilledButton.styleFrom(
                      backgroundColor: Theme.of(context).colorScheme.error)
                  : null,
              onPressed: () => Navigator.pop(context, true),
              child: Text(action)),
        ],
      ),
    );
    return result == true && mounted;
  }

  Future<void> _publish() async {
    if (await _confirm('Publish this video?',
        'Anyone on KoloVibe will be able to watch it.', 'Publish')) {
      await controller.publish();
    }
  }

  Future<void> _unpublish() async {
    if (await _confirm(
        'Unpublish this video?',
        'It will no longer be visible to others. You can publish it again.',
        'Unpublish')) {
      await controller.unpublish();
    }
  }

  Future<void> _delete() async {
    if (await _confirm(
        'Delete this video?',
        'It will be removed from your library and from KoloVibe. This cannot be undone from the app.',
        'Delete',
        destructive: true)) {
      await controller.delete();
    }
  }

  Future<void> _edit(OwnedVideo video) async {
    final result = await showDialog<_Edit>(
        context: context, builder: (context) => _EditDialog(video: video));
    if (result == null || !mounted) return;
    await controller.edit(
        title: result.title,
        description: result.description,
        category: result.category,
        tags: result.tags);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Manage video')),
        body: SafeArea(
            child: ListenableBuilder(
                listenable: controller,
                builder: (context, _) => _body(context))),
      );

  Widget _body(BuildContext context) {
    switch (controller.phase) {
      case ManagePhase.loading:
        return const LiveStateView.loading(label: 'Loading your video');
      case ManagePhase.failed:
        return LiveStateView.failure(controller.loadError!,
            onRetry: controller.load,
            onSignIn: () => signInThenReturn(context, 40));
      case ManagePhase.ready:
        return _ready(context, controller.video!);
    }
  }

  Widget _ready(BuildContext context, OwnedVideo video) {
    final theme = Theme.of(context);
    final busy = controller.busy;
    final published = video.publishedAt;
    return ListView(padding: const EdgeInsets.all(16), children: [
      if (video.posterUrl != null)
        ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: AspectRatio(
                aspectRatio: 16 / 9,
                // A short-lived signed link: shown, never stored.
                child: Image.network(video.posterUrl!,
                    fit: BoxFit.cover,
                    excludeFromSemantics: true,
                    errorBuilder: (_, __, ___) => const ColoredBox(
                        color: Colors.black12,
                        child: Center(child: Icon(Icons.movie_outlined)))))),
      const SizedBox(height: 12),
      Text(video.title, style: theme.textTheme.titleLarge),
      const SizedBox(height: 4),
      Semantics(
          label: 'Status: ${videoStateLabel(video)}',
          child: Text(videoStateLabel(video),
              style: theme.textTheme.titleSmall
                  ?.copyWith(color: theme.colorScheme.primary))),
      if (video.description.isNotEmpty) ...[
        const SizedBox(height: 8),
        Text(video.description),
      ],
      if (published != null) ...[
        const SizedBox(height: 8),
        Text('Approved ${published.toLocal().toString().split(' ').first}',
            style: theme.textTheme.bodySmall),
      ],
      if (controller.message != null)
        Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Semantics(
                liveRegion: true,
                child: Text(controller.message!,
                    style: TextStyle(
                        color: controller.sessionExpired
                            ? theme.colorScheme.error
                            : null)))),
      if (controller.sessionExpired)
        Align(
            alignment: Alignment.centerLeft,
            child: TextButton(
                onPressed: () => signInThenReturn(context, 40),
                child: const Text('Sign in'))),
      const SizedBox(height: 16),
      if (video.canPublish)
        FilledButton(
            onPressed: busy ? null : _publish, child: const Text('Publish')),
      if (video.canUnpublish)
        OutlinedButton(
            onPressed: busy ? null : _unpublish,
            child: const Text('Unpublish')),
      if (video.state == 'review')
        const Text(
            'A reviewer is checking this video. You will be able to publish it once it is approved.'),
      if (video.state == 'processing' || video.state == 'uploading')
        const Text('Your video is still being prepared. Check back shortly.'),
      if (video.state == 'rejected' || video.state == 'removed')
        TextButton(
            onPressed: () => Navigator.of(context).pushNamed(
                const ScreenRoute(76).name,
                arguments: ScreenRoute(76, entityId: video.id)),
            child: const Text('View notice')),
      if (video.canEditDetails)
        TextButton(
            onPressed: busy ? null : () => _edit(video),
            child: const Text('Edit details')),
      TextButton(
          style: TextButton.styleFrom(foregroundColor: theme.colorScheme.error),
          onPressed: busy ? null : _delete,
          child: const Text('Delete video')),
      if (busy)
        const Padding(
            padding: EdgeInsets.only(top: 12),
            child: Center(child: CircularProgressIndicator())),
    ]);
  }
}

class _Edit {
  const _Edit(this.title, this.description, this.category, this.tags);
  final String title, description;
  final String? category;
  final List<String> tags;
}

class _EditDialog extends StatefulWidget {
  const _EditDialog({required this.video});
  final OwnedVideo video;

  @override
  State<_EditDialog> createState() => _EditDialogState();
}

class _EditDialogState extends State<_EditDialog> {
  final _form = GlobalKey<FormState>();
  late final _title = TextEditingController(text: widget.video.title);
  late final _description =
      TextEditingController(text: widget.video.description);
  late final _tags = TextEditingController(text: widget.video.tags.join(' '));
  late String? _category = widget.video.category;

  @override
  void dispose() {
    _title.dispose();
    _description.dispose();
    _tags.dispose();
    super.dispose();
  }

  String? _tagError(String? value) {
    try {
      normalizeTags((value ?? '').split(RegExp(r'[\s,]+')));
      return null;
    } on FormatException {
      return 'Use up to five tags: letters, numbers and underscores';
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
        title: const Text('Edit details'),
        content: Form(
          key: _form,
          child: SingleChildScrollView(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              TextFormField(
                  controller: _title,
                  maxLength: 160,
                  decoration: const InputDecoration(labelText: 'Title'),
                  validator: (value) => value == null || value.trim().isEmpty
                      ? 'Enter a title'
                      : null),
              TextFormField(
                  controller: _description,
                  maxLength: 2000,
                  maxLines: 3,
                  decoration: const InputDecoration(labelText: 'Description')),
              DropdownButtonFormField<String>(
                  initialValue: _category,
                  decoration: const InputDecoration(labelText: 'Category'),
                  items: [
                    for (final entry in videoCategories.entries)
                      DropdownMenuItem(
                          value: entry.key, child: Text(entry.value))
                  ],
                  onChanged: (value) => _category = value),
              TextFormField(
                  controller: _tags,
                  decoration: const InputDecoration(labelText: 'Hashtags'),
                  validator: _tagError),
            ]),
          ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () {
                if (_form.currentState?.validate() ?? false) {
                  Navigator.pop(
                      context,
                      _Edit(
                          _title.text,
                          _description.text,
                          _category,
                          _tags.text
                              .split(RegExp(r'[\s,]+'))
                              .where((tag) => tag.isNotEmpty)
                              .toList()));
                }
              },
              child: const Text('Save')),
        ],
      );
}
