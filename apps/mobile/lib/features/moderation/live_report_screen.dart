import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import '../../core/presentation/design_node.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/live_state_view.dart';
import '../discovery/live_video_repository.dart';
import '../shell/main_shell.dart';
import 'live_moderation_repository.dart';
import 'report_controller.dart';

/// Report a video (M-071–M-075).
///
/// A report is private and never removes a video by itself. The server decides
/// acceptance, duplicates and outcomes; this screen only sends the person's
/// choice and shows the server's answer.
class LiveReportScreen extends StatefulWidget {
  const LiveReportScreen(
      {super.key,
      required this.route,
      required this.catalog,
      required this.videos,
      required this.moderation,
      this.controller});
  final ScreenRoute route;
  final DesignCatalog catalog;
  final LiveVideoRepository videos;
  final LiveModerationRepository moderation;

  /// Test seam for a pre-built controller.
  final ReportController? controller;

  @override
  State<LiveReportScreen> createState() => _LiveReportScreenState();
}

class _LiveReportScreenState extends State<LiveReportScreen> {
  late final ReportController controller;
  final details = TextEditingController();

  @override
  void initState() {
    super.initState();
    final id = widget.route.entityId;
    controller = widget.controller ??
        ReportController(widget.videos, widget.moderation, id ?? '',
            lookup: switch (widget.route.screen) {
              73 => ReportLookup.latest,
              75 => ReportLookup.openOnly,
              _ => ReportLookup.none,
            });
    controller.addListener(_syncDetails);
    if (id == null || !isApiId(id)) {
      controller
        ..phase = ReportPhase.failed
        ..loadError = const ApiFailure(404, 'Choose a video before reporting.');
    } else {
      controller.load();
    }
  }

  /// Keeps the text field in step with the controller, so a sent report's
  /// text is cleared and a retry shows what was typed.
  void _syncDetails() {
    if (details.text != controller.details) {
      details.value = TextEditingValue(
          text: controller.details,
          selection:
              TextSelection.collapsed(offset: controller.details.length));
    }
  }

  @override
  void dispose() {
    controller.removeListener(_syncDetails);
    // The report text is private: clear it from memory when leaving.
    details.clear();
    details.dispose();
    controller.setDetails('');
    controller.dispose();
    super.dispose();
  }

  void go(int target) {
    final route = ScreenRoute(target,
        entityId: target == 24 || target == 87
            ? null
            : controller.video?.id ?? widget.route.entityId);
    Navigator.of(context).pushNamed(route.name, arguments: route);
  }

  String get _title => switch (controller.stage) {
        ReportStage.reason => 'Report a video',
        ReportStage.details => 'Report details',
        ReportStage.submitted => 'Report submitted',
        ReportStage.alreadyReported => 'Already reported',
        ReportStage.error => 'Report submission error',
      };

  void _back() {
    switch (controller.stage) {
      case ReportStage.details:
        controller.backToReason();
      case ReportStage.error:
        controller.backToDetails();
      case ReportStage.reason ||
            ReportStage.submitted ||
            ReportStage.alreadyReported:
        Navigator.maybePop(context);
    }
  }

  @override
  Widget build(BuildContext context) {
    final navigation =
        widget.catalog[widget.route.screen].named('Primary navigation');
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) => Scaffold(
        appBar: AppBar(
            title: Text(controller.phase == ReportPhase.ready
                ? _title
                : 'Report a video'),
            backgroundColor: KoloVibeColors.lavender,
            leading: IconButton(
                tooltip: 'Back',
                icon: SvgPicture.asset('assets/images/add18c048fedbc53b74e.svg',
                    width: 24, height: 24),
                onPressed: _back)),
        body: SafeArea(child: _body(context)),
        bottomNavigationBar: navigation == null
            ? null
            : MainShell(
                navigation: navigation,
                screen: widget.route.screen,
                onSelected: go),
      ),
    );
  }

  Widget _body(BuildContext context) {
    switch (controller.phase) {
      case ReportPhase.loading:
        return const LiveStateView.loading(label: 'Loading the video');
      case ReportPhase.failed:
        final error = controller.loadError!;
        if (error is ApiFailure && error.kind == FailureKind.notFound) {
          return LiveStateView.empty(
              title: 'Video not available',
              message: error.status == 404 && widget.route.entityId == null
                  ? error.message
                  : 'This video is no longer available to report.',
              icon: Icons.search_off,
              actionLabel: 'Return to videos',
              onAction: () => go(24));
        }
        return LiveStateView.failure(error,
            onRetry: controller.load, onSignIn: _signIn);
      case ReportPhase.ready:
        return ListView(
            padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
            children: [_videoCard(), ..._stage(context)]);
    }
  }

  void _signIn() =>
      Navigator.of(context).pushNamed(const ScreenRoute(4, returnTo: 24).name,
          arguments: const ScreenRoute(4, returnTo: 24));

  Widget _videoCard() => Card(
      child: Padding(
          padding: const EdgeInsets.all(16),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(controller.video!.title,
                style: const TextStyle(
                    fontWeight: FontWeight.w700, color: KoloVibeColors.navy)),
            Text(
                switch (controller.stage) {
                  ReportStage.submitted => 'Reported privately',
                  ReportStage.alreadyReported => 'Previously reported',
                  ReportStage.details || ReportStage.error => 'Selected video',
                  ReportStage.reason => 'Reporting privately',
                },
                style: const TextStyle(color: KoloVibeColors.muted)),
          ])));

  List<Widget> _stage(BuildContext context) => switch (controller.stage) {
        ReportStage.reason => _reason(context),
        ReportStage.details => _details(context),
        ReportStage.submitted => _submitted(context),
        ReportStage.alreadyReported => _already(context),
        ReportStage.error => _error(context),
      };

  List<Widget> _reason(BuildContext context) => [
        const SizedBox(height: 16),
        Semantics(
            header: true,
            child: Text('What’s your concern?',
                style: Theme.of(context).textTheme.titleMedium)),
        for (final option in reportReasons)
          Semantics(
              inMutuallyExclusiveGroup: true,
              checked: identical(controller.reason, option),
              child: ListTile(
                  title: Text(option.label),
                  trailing: Icon(identical(controller.reason, option)
                      ? Icons.radio_button_checked
                      : Icons.radio_button_unchecked),
                  onTap: () => controller.choose(option))),
        FilledButton(
            style: FilledButton.styleFrom(backgroundColor: KoloVibeColors.red),
            onPressed: controller.canContinue ? controller.toDetails : null,
            child: const Text('Continue')),
        const Text('Choose the closest reason. You can add context next.',
            style: TextStyle(color: KoloVibeColors.muted)),
      ];

  List<Widget> _details(BuildContext context) {
    return [
      const SizedBox(height: 16),
      Chip(label: Text(controller.reason!.label)),
      const SizedBox(height: 16),
      TextField(
          controller: details,
          maxLength: 2000,
          maxLines: 5,
          enabled: !controller.submitting,
          onChanged: controller.setDetails,
          decoration: const InputDecoration(
              labelText: 'Additional details · Optional')),
      const Card(
          color: KoloVibeColors.softBlue,
          child: Padding(
              padding: EdgeInsets.all(16),
              child: Text(
                  'Your report is private. Include only relevant details. Do not add passwords or sensitive personal information.'))),
      FilledButton(
          style: FilledButton.styleFrom(backgroundColor: KoloVibeColors.red),
          onPressed: controller.submitting ? null : controller.submit,
          child: Text(controller.submitting ? 'Submitting…' : 'Submit report')),
      const Text(
          'A reason is required. Supporting text is optional. A report does not automatically remove content.',
          style: TextStyle(color: KoloVibeColors.muted)),
    ];
  }

  List<Widget> _submitted(BuildContext context) {
    final record = controller.existing;
    final reviewed =
        controller.receipt == null && record != null && record.status != 'open';
    final reason = record?.reason ?? controller.reason?.code;
    return [
      const SizedBox(height: 24),
      Semantics(
          liveRegion: true,
          child: Text('Thank you for speaking up.',
              style: Theme.of(context).textTheme.headlineMedium)),
      const SizedBox(height: 12),
      Text(reviewed
          ? 'Your report about ${controller.video!.title} has been reviewed.'
          : 'Your report about ${controller.video!.title} has been submitted for review under the applicable guidelines.'),
      const SizedBox(height: 12),
      Card(
          child: ListTile(
              title: Text(controller.video!.title),
              subtitle: Text(reason == null
                  ? 'Reported privately'
                  : 'Reported privately · ${reportReasonLabel(reason)}'))),
      const SizedBox(height: 12),
      Text('What happens next', style: Theme.of(context).textTheme.titleMedium),
      const Text(
          'Reporting doesn’t automatically remove a video. We can share only information permitted by the review policy.'),
      const SizedBox(height: 16),
      FilledButton(
          onPressed: () => go(24), child: const Text('Return to videos')),
      TextButton(
          onPressed: () => go(87),
          child: const Text('Read community guidelines')),
    ];
  }

  List<Widget> _already(BuildContext context) {
    final record = controller.existing;
    return [
      const SizedBox(height: 24),
      Semantics(
          liveRegion: true,
          child: Text('Your concern is already recorded.',
              style: Theme.of(context).textTheme.headlineMedium)),
      const SizedBox(height: 12),
      const Text(
          'You’ve already submitted a report about this video. You don’t need to submit the same concern again.'),
      const SizedBox(height: 12),
      Card(
          child: ListTile(
              title: Text(controller.video!.title),
              subtitle: Text(record == null
                  ? 'Previously reported'
                  : 'Previously reported · ${reportReasonLabel(record.reason)}'))),
      const SizedBox(height: 12),
      Text('No duplicate report was created',
          style: Theme.of(context).textTheme.titleMedium),
      const Text(
          'The video’s availability is determined separately under the review policy.'),
      const SizedBox(height: 16),
      FilledButton(
          onPressed: () => go(24), child: const Text('Return to videos')),
      TextButton(
          onPressed: () => go(87), child: const Text('Community guidelines')),
    ];
  }

  List<Widget> _error(BuildContext context) {
    final failure = controller.submitFailure;
    final kind = failure is ApiFailure ? failure.kind : FailureKind.unavailable;
    final (title, message, retry) = switch (kind) {
      FailureKind.expired => (
          'Session expired',
          'Sign in again, then reopen the video to report it. Your report was not sent.',
          false
        ),
      FailureKind.forbidden => (
          'Report not accepted',
          'You can’t report this video right now. Your report was not sent.',
          false
        ),
      FailureKind.notFound => (
          'Video not available',
          'This video is no longer available to report. Your report was not sent.',
          false
        ),
      FailureKind.rateLimited => (
          'Too many reports',
          'Wait a moment, then try again.',
          true
        ),
      FailureKind.invalid => (
          'Report not accepted',
          'Your report could not be accepted. Review your details and try again.',
          false
        ),
      FailureKind.conflict => (
          'Report not confirmed',
          'This report conflicts with an earlier attempt. Review your details and try again.',
          true
        ),
      _ => (
          'Submission interrupted',
          'The service did not confirm your report. Check your connection and try again.',
          true
        ),
    };
    return [
      const SizedBox(height: 16),
      Semantics(
          liveRegion: true,
          child: Text('Report not confirmed',
              style: Theme.of(context).textTheme.headlineMedium)),
      const SizedBox(height: 8),
      const Text('We couldn’t send your report.'),
      const SizedBox(height: 8),
      Card(
          color: KoloVibeColors.softBlue,
          child: ListTile(title: Text(title), subtitle: Text(message))),
      if (controller.reason != null) ...[
        Text('Your selected reason',
            style: Theme.of(context).textTheme.titleMedium),
        Text(controller.reason!.label),
      ],
      if (kind != FailureKind.expired)
        const Text(
            'Your text remains on this screen while you retry. Leaving may discard it.',
            style: TextStyle(color: KoloVibeColors.muted)),
      const SizedBox(height: 16),
      if (kind == FailureKind.expired)
        FilledButton(onPressed: _signIn, child: const Text('Sign in'))
      else if (retry)
        FilledButton(
            style: FilledButton.styleFrom(backgroundColor: KoloVibeColors.red),
            onPressed: controller.submitting ? null : controller.submit,
            child: Text(controller.submitting
                ? 'Submitting…'
                : 'Try submitting again')),
      if (kind != FailureKind.expired &&
          kind != FailureKind.forbidden &&
          kind != FailureKind.notFound)
        TextButton(
            onPressed: controller.backToDetails,
            child: const Text('Return to report details')),
      TextButton(
          onPressed: () => Navigator.maybePop(context),
          child: const Text('Cancel report')),
    ];
  }
}
