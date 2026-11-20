import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import '../../app/screen_route.dart';
import '../../core/presentation/design_node.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/kolo_components.dart';
import '../../shared/widgets/kolo_media.dart';
import '../../shared/widgets/live_state_view.dart';
import '../creators/live_analytics_repository.dart';
import '../creators/live_analytics_screen.dart' show analyticsCount;
import '../discovery/home_dashboard.dart' show categoryLabel;
import '../discovery/live_video_repository.dart' show formatDuration;
import '../creators/creator_shell.dart';
import 'live_content_repository.dart';
import 'manage_video_controller.dart';

/// M-053 Manage video with M-055 (unpublish) and M-056 (delete) confirmations and M-054 detail editing.
class LiveManageVideoScreen extends StatefulWidget {
  const LiveManageVideoScreen(
      {super.key,
      required this.videoId,
      required this.repository,
      this.analytics,
      this.catalog,
      this.controller});

  final String videoId;
  final LiveContentRepository repository;

  /// Reads this video's qualified plays and likes for the hero (optional).
  final LiveAnalyticsRepository? analytics;

  /// Supplies the designed bottom navigation.
  final DesignCatalog? catalog;

  /// Test seam for a pre-built controller.
  final ManageVideoController? controller;

  @override
  State<LiveManageVideoScreen> createState() => _LiveManageVideoScreenState();
}

class _LiveManageVideoScreenState extends State<LiveManageVideoScreen> {
  late final ManageVideoController controller;
  VideoAnalytics? stats;

  @override
  void initState() {
    super.initState();
    _loadStats();
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

  /// Optional: when analytics are closed or fail, the hero shows no figures.
  Future<void> _loadStats() async {
    final repository = widget.analytics;
    if (repository == null) return;
    try {
      final value = await repository.video(widget.videoId, 'since_published');
      if (mounted) setState(() => stats = value);
    } catch (_) {
      if (mounted) setState(() => stats = null);
    }
  }

  void _closeWhenDeleted() {
    if (controller.deleted && mounted) Navigator.of(context).pop(true);
  }

  Future<bool> _confirm(String title, String body, String action,
      {bool destructive = false, String? typed}) async {
    final result = await showDialog<bool>(
      context: context,
      builder: (context) => _ConfirmDialog(
          title: title,
          body: body,
          action: action,
          destructive: destructive,
          typed: typed),
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
        'Take this video off stage?',
        '${controller.video?.title ?? 'This video'} will no longer be viewable by others. This is different from deleting: your library will show its updated publication status and you can publish it again.',
        'Unpublish video')) {
      await controller.unpublish();
    }
  }

  Future<void> _delete() async {
    if (await _confirm(
        'Delete this original?',
        'You’re deleting ${controller.video?.title ?? 'this video'} from your library. This is different from unpublishing. Don’t continue unless you intend to remove it. This cannot be undone from the app.',
        'Delete video',
        destructive: true,
        typed: 'DELETE')) {
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
        tags: result.tags,
        coverTimeMs: result.coverTimeMs);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Manage video')),
        body: SafeArea(
            child: ListenableBuilder(
                listenable: controller,
                builder: (context, _) => _body(context))),
        bottomNavigationBar: widget.catalog == null
            ? null
            : creatorNavigation(context, widget.catalog!, 53),
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
    final meta = [
      if (video.category != null) categoryLabel(video.category!),
      if (formatDuration(video.durationMs) != null)
        formatDuration(video.durationMs)!,
    ].join(' · ');
    return ListView(
        padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
        children: [
          // Hero: the poster is a short-lived signed link, shown and never stored.
          ClipRRect(
              borderRadius: BorderRadius.circular(KoloVibeRadii.card),
              child: Stack(children: [
                AspectRatio(
                    aspectRatio: 342 / 198,
                    child: KoloPoster(
                        url: video.posterUrl == null
                            ? null
                            : Uri.tryParse(video.posterUrl!),
                        iconSize: 40)),
                const Positioned.fill(
                    child: DecoratedBox(
                        decoration: BoxDecoration(
                            gradient: LinearGradient(
                                begin: Alignment.topCenter,
                                end: Alignment.bottomCenter,
                                colors: [
                      Color(0x21001539),
                      Color(0xF5001539)
                    ])))),
                Positioned(
                    left: 18,
                    right: 18,
                    bottom: 18,
                    child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('KOLOVIBE ORIGINAL',
                              style: KoloVibeText.body(10,
                                  weight: FontWeight.w700,
                                  color: KoloVibeColors.gold,
                                  letterSpacing: 0.6)),
                          const SizedBox(height: 8),
                          Text(video.title,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: KoloVibeText.heading(26,
                                  color: Colors.white, height: 1.15)),
                          if (meta.isNotEmpty) ...[
                            const SizedBox(height: 6),
                            Text(meta,
                                style:
                                    KoloVibeText.body(11, color: Colors.white)),
                          ],
                        ])),
              ])),
          const SizedBox(height: 12),
          Wrap(spacing: 8, runSpacing: 8, children: [
            Semantics(
                label: 'Status: ${videoStateLabel(video)}',
                excludeSemantics: true,
                child: KoloBadge(videoStateLabel(video), filled: true)),
            if (video.category != null)
              KoloBadge(categoryLabel(video.category!)),
          ]),
          if (stats != null) ...[
            const SizedBox(height: 16),
            Row(children: [
              for (final (label, value) in [
                ('Qualified plays', analyticsCount(stats!.qualifiedPlays)),
                ('Likes', analyticsCount(stats!.currentLikes)),
              ])
                Expanded(
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                      Text(label, style: KoloVibeText.body(11)),
                      const SizedBox(height: 5),
                      Text(value, style: KoloVibeText.heading(26)),
                    ])),
            ]),
          ],
          if (video.description.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(video.description, style: KoloVibeText.body(14, height: 1.5)),
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
                onPressed: busy ? null : _publish,
                child: const Text('Publish')),
          if (video.state == 'review')
            const Text(
                'A reviewer is checking this video. You will be able to publish it once it is approved.'),
          if (video.state == 'processing' || video.state == 'uploading')
            const Text(
                'Your video is still being prepared. Check back shortly.'),
          const SizedBox(height: 8),
          if (widget.analytics != null && video.state == 'published')
            KoloListRow(
                title: 'View analytics',
                subtitle: 'Qualified activity and watch time',
                onTap: () => Navigator.of(context).pushNamed(
                    const ScreenRoute(59).name,
                    arguments: ScreenRoute(59, entityId: video.id))),
          if (video.canEditDetails)
            KoloListRow(
                title: 'Edit details',
                subtitle: 'Title, description, category, hashtags and cover',
                onTap: busy ? null : () => _edit(video)),
          if (video.canUnpublish)
            KoloListRow(
                title: 'Unpublish',
                subtitle: 'Remove from public viewing',
                onTap: busy ? null : _unpublish),
          if (video.state == 'rejected' || video.state == 'removed')
            KoloListRow(
                title: 'View notice',
                onTap: () => Navigator.of(context).pushNamed(
                    const ScreenRoute(76).name,
                    arguments: ScreenRoute(76, entityId: video.id))),
          KoloListRow(
              title: 'Delete video',
              destructive: true,
              divider: false,
              onTap: busy ? null : _delete),
          if (busy)
            const Padding(
                padding: EdgeInsets.only(top: 12),
                child: Center(child: CircularProgressIndicator())),
        ]);
  }
}

/// The designed confirmation dialog: an alert mark, a title, an explanation
/// and a red action with a soft Cancel. [typed] adds the "Type DELETE to
/// confirm" field that must match before the action is enabled.
class _ConfirmDialog extends StatefulWidget {
  const _ConfirmDialog(
      {required this.title,
      required this.body,
      required this.action,
      required this.destructive,
      this.typed});
  final String title, body, action;
  final bool destructive;
  final String? typed;

  @override
  State<_ConfirmDialog> createState() => _ConfirmDialogState();
}

class _ConfirmDialogState extends State<_ConfirmDialog> {
  final _typed = TextEditingController();

  @override
  void dispose() {
    _typed.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
        key: ValueKey(widget.typed == null ? 'M-055' : 'M-056'),
        scrollable: true,
        icon: Align(
            alignment: Alignment.centerLeft,
            child: SvgPicture.asset(KoloIcons.circleAlert,
                width: 24, height: 24, excludeFromSemantics: true)),
        iconPadding: const EdgeInsets.fromLTRB(24, 24, 24, 0),
        title: Text(widget.title),
        content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(widget.body),
              if (widget.typed != null) ...[
                const SizedBox(height: 16),
                KoloTextField(
                    label: 'Type ${widget.typed} to confirm',
                    controller: _typed,
                    hint: widget.typed,
                    onChanged: (_) => setState(() {})),
              ],
            ]),
        actionsAlignment: MainAxisAlignment.center,
        actionsOverflowDirection: VerticalDirection.down,
        actions: [
          ListenableBuilder(
              listenable: _typed,
              builder: (context, _) => FilledButton(
                  onPressed:
                      widget.typed != null && _typed.text.trim() != widget.typed
                          ? null
                          : () => Navigator.pop(context, true),
                  child: Text(widget.action))),
          OutlinedButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
        ],
      );
}

class _Edit {
  const _Edit(
      this.title, this.description, this.category, this.tags, this.coverTimeMs);
  final String title, description;
  final String? category;
  final int? coverTimeMs;
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
  late int? _cover = widget.video.coverTimeMs;

  String _clock(int ms) {
    final seconds = ms ~/ 1000;
    return '${seconds ~/ 60}:${(seconds % 60).toString().padLeft(2, '0')}';
  }

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
                  isExpanded: true,
                  initialValue: _category,
                  decoration: const InputDecoration(labelText: 'Category'),
                  items: [
                    for (final entry in videoCategories.entries)
                      DropdownMenuItem(
                          value: entry.key,
                          child: Text(entry.value,
                              overflow: TextOverflow.ellipsis))
                  ],
                  onChanged: (value) => _category = value),
              TextFormField(
                  controller: _tags,
                  decoration: const InputDecoration(labelText: 'Hashtags'),
                  validator: _tagError),
              // Cover (M-045): the service renders the poster at a chosen
              // moment. It can only be bounded once the duration is known, and
              // the service does not offer frame previews.
              if (widget.video.durationMs case final duration?
                  when duration > 0) ...[
                const SizedBox(height: 16),
                Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                        'Cover moment · ${_clock(_cover ?? 0)} of ${_clock(duration)}',
                        style: Theme.of(context).textTheme.labelMedium)),
                Slider(
                    key: const ValueKey('Cover moment'),
                    min: 0,
                    max: (duration < 300000 ? duration : 300000).toDouble(),
                    divisions: ((duration < 300000 ? duration : 300000) ~/ 1000)
                        .clamp(1, 300),
                    value: (_cover ?? 0)
                        .clamp(0, duration < 300000 ? duration : 300000)
                        .toDouble(),
                    label: _clock(_cover ?? 0),
                    onChanged: (value) =>
                        setState(() => _cover = value.round())),
                Text(
                    'The service picks the poster image at this moment. A new poster appears after processing.',
                    style: Theme.of(context).textTheme.bodySmall),
              ],
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
                              .toList(),
                          _cover));
                }
              },
              child: const Text('Save')),
        ],
      );
}
