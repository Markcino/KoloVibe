import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import '../../core/presentation/design_node.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../discovery/live_video_repository.dart';
import '../shell/main_shell.dart';
import 'live_moderation_repository.dart';

class LiveReportScreen extends StatefulWidget {
  const LiveReportScreen(
      {super.key,
      required this.route,
      required this.catalog,
      required this.videos,
      required this.moderation});
  final ScreenRoute route;
  final DesignCatalog catalog;
  final LiveVideoRepository videos;
  final LiveModerationRepository moderation;

  @override
  State<LiveReportScreen> createState() => _LiveReportScreenState();
}

class _LiveReportScreenState extends State<LiveReportScreen> {
  static const reasons = <String, String>{
    'Harassment or hateful content': 'harassment',
    'Violence or harmful activity': 'harmful',
    'Sexual or inappropriate content': 'harmful',
    'Rights or ownership concern': 'copyright',
    'Spam or misleading content': 'spam',
    'Something else': 'other',
  };

  final details = TextEditingController();
  late final String key = LiveModerationRepository.newIdempotencyKey();
  LiveVideo? video;
  ModerationReceipt? receipt;
  String? selected;
  String? error;
  bool loading = true, submitting = false;
  int step = 0;

  @override
  void initState() {
    super.initState();
    step = widget.route.screen == 72 ? 1 : 0;
    load();
  }

  @override
  void dispose() {
    details.clear();
    details.dispose();
    super.dispose();
  }

  Future<void> load() async {
    final id = widget.route.entityId;
    if (id == null || !isApiId(id)) {
      setState(() {
        loading = false;
        error = 'Choose a video before reporting.';
      });
      return;
    }
    try {
      final value = await widget.videos.detail(id);
      if (mounted) setState(() => video = value);
      if ({73, 75}.contains(widget.route.screen)) {
        final reports = await widget.moderation.ownReports();
        final matches = reports.where((report) => report.videoId == id);
        if (mounted && matches.isNotEmpty) {
          setState(() => receipt = matches.first);
        }
      }
    } catch (failure) {
      if (mounted) {
        setState(() => error = failure is ApiFailure
            ? failure.message
            : 'The report service is unavailable.');
      }
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> send() async {
    if (submitting || selected == null || video == null) {
      setState(() => error = 'Choose a reason before submitting.');
      return;
    }
    setState(() {
      submitting = true;
      error = null;
    });
    try {
      final value = await widget.moderation.report(
          videoId: video!.id,
          reason: reasons[selected]!,
          details: details.text.trim(),
          key: key);
      details.clear();
      if (mounted) setState(() => receipt = value);
    } catch (failure) {
      if (mounted) {
        setState(() => error = failure is ApiFailure
            ? failure.message
            : 'The report was not confirmed. Check your connection and retry.');
      }
    } finally {
      if (mounted) setState(() => submitting = false);
    }
  }

  void go(int target) {
    final route =
        ScreenRoute(target, entityId: video?.id ?? widget.route.entityId);
    Navigator.of(context).pushNamed(route.name, arguments: route);
  }

  @override
  Widget build(BuildContext context) {
    final navigation =
        widget.catalog[widget.route.screen].named('Primary navigation');
    return Scaffold(
      appBar: AppBar(
          title: Text(receipt != null
              ? 'Report submitted'
              : step == 0
                  ? 'Report a video'
                  : 'Report details'),
          backgroundColor: KoloVibeColors.lavender,
          leading: IconButton(
              tooltip: 'Back',
              icon: SvgPicture.asset('assets/images/add18c048fedbc53b74e.svg',
                  width: 24, height: 24),
              onPressed: () => step == 1 && receipt == null
                  ? setState(() => step = 0)
                  : Navigator.maybePop(context))),
      body: SafeArea(
          child: ListView(
              padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
              children: [
            if (loading) const Center(child: CircularProgressIndicator()),
            if (error != null)
              Padding(
                  padding: const EdgeInsets.only(bottom: 16),
                  child: Semantics(
                      liveRegion: true,
                      child: Text(error!,
                          style: const TextStyle(color: KoloVibeColors.red)))),
            if (video != null)
              Card(
                  child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(video!.title,
                                style: const TextStyle(
                                    fontWeight: FontWeight.w700,
                                    color: KoloVibeColors.navy)),
                            const Text('Reporting privately',
                                style: TextStyle(color: KoloVibeColors.muted)),
                          ]))),
            if (video != null && receipt == null && step == 0) ...[
              const SizedBox(height: 16),
              Text('What’s your concern?',
                  style: Theme.of(context).textTheme.titleMedium),
              for (final label in reasons.keys)
                ListTile(
                    title: Text(label),
                    trailing: Icon(selected == label
                        ? Icons.radio_button_checked
                        : Icons.radio_button_unchecked),
                    onTap: () => setState(() => selected = label)),
              FilledButton(
                  style: FilledButton.styleFrom(
                      backgroundColor: KoloVibeColors.red),
                  onPressed:
                      selected == null ? null : () => setState(() => step = 1),
                  child: const Text('Continue')),
              const Text('Choose the closest reason. You can add context next.',
                  style: TextStyle(color: KoloVibeColors.muted)),
            ],
            if (video != null && receipt == null && step == 1) ...[
              const SizedBox(height: 16),
              Chip(label: Text(selected ?? 'Choose a reason above')),
              const SizedBox(height: 16),
              TextField(
                  controller: details,
                  maxLength: 2000,
                  maxLines: 5,
                  decoration: const InputDecoration(
                      labelText: 'Additional details · Optional')),
              const Card(
                  color: KoloVibeColors.softBlue,
                  child: Padding(
                      padding: EdgeInsets.all(16),
                      child: Text(
                          'Your report is private. Include only relevant details. Do not add passwords or sensitive personal information.'))),
              FilledButton(
                  style: FilledButton.styleFrom(
                      backgroundColor: KoloVibeColors.red),
                  onPressed: submitting || selected == null ? null : send,
                  child: Text(submitting ? 'Submitting…' : 'Submit report')),
              const Text('A report does not automatically remove content.',
                  style: TextStyle(color: KoloVibeColors.muted)),
            ],
            if (receipt != null) ...[
              const SizedBox(height: 24),
              Text('Thank you for speaking up.',
                  style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 12),
              Text('Your report about ${video!.title} is ${receipt!.status}.'),
              const SizedBox(height: 20),
              const Text('Reporting does not automatically remove a video.'),
              FilledButton(
                  onPressed: () => go(24),
                  child: const Text('Return to videos')),
              TextButton(
                  onPressed: () => go(87),
                  child: const Text('Read community guidelines')),
            ],
          ])),
      bottomNavigationBar: navigation == null
          ? null
          : MainShell(
              navigation: navigation,
              screen: widget.route.screen,
              onSelected: go),
    );
  }
}
