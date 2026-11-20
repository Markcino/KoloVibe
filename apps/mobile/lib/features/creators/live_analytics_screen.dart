import 'package:flutter/material.dart';
import '../../core/network/api_client.dart';
import '../../core/presentation/design_node.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/kolo_components.dart';
import '../content/live_content_repository.dart';
import '../system/system_ui.dart';
import 'creator_shell.dart';
import 'live_analytics_repository.dart';

/// "21 OCT" style label used under the chart.
String chartDate(DateTime value) {
  const months = [
    'JAN',
    'FEB',
    'MAR',
    'APR',
    'MAY',
    'JUN',
    'JUL',
    'AUG',
    'SEP',
    'OCT',
    'NOV',
    'DEC'
  ];
  return '${value.day.toString().padLeft(2, '0')} ${months[value.month - 1]}';
}

/// 18.2K / 1,826 style counts: the design abbreviates five-digit values.
String analyticsCount(int value) {
  if (value >= 1000000) {
    return '${(value / 1000000).toStringAsFixed(value >= 10000000 ? 0 : 1)}M';
  }
  if (value >= 10000) return '${(value / 1000).toStringAsFixed(1)}K';
  final digits = value.toString();
  return digits.length <= 3
      ? digits
      : '${digits.substring(0, digits.length - 3)},${digits.substring(digits.length - 3)}';
}

/// 438h / 12m / 40s watch time.
String watchTime(double seconds) {
  if (seconds >= 3600) return '${(seconds / 3600).round()}h';
  if (seconds >= 60) return '${(seconds / 60).round()}m';
  return '${seconds.round()}s';
}

/// 02:07 average watch.
String clockTime(double seconds) {
  final total = seconds.round();
  return '${(total ~/ 60).toString().padLeft(2, '0')}:${(total % 60).toString().padLeft(2, '0')}';
}

/// M-058 Creator analytics, M-059 Video analytics and M-060 (the empty or
/// unavailable state of either). Numbers come from the creator's own analytics
/// endpoints; a zero-activity or unavailable response shows dashes, never zero
/// performance, as the design states.
class LiveAnalyticsScreen extends StatefulWidget {
  const LiveAnalyticsScreen({
    super.key,
    required this.catalog,
    required this.analytics,
    this.content,
    this.videoId,
  });
  final DesignCatalog catalog;
  final LiveAnalyticsRepository analytics;
  final LiveContentRepository? content;

  /// Set for M-059.
  final String? videoId;

  @override
  State<LiveAnalyticsScreen> createState() => _LiveAnalyticsScreenState();
}

class _LiveAnalyticsScreenState extends State<LiveAnalyticsScreen> {
  String range = '7d';
  bool loading = true;
  Object? error;
  CreatorAnalytics? creator;
  VideoAnalytics? video;
  OwnedVideo? owned;
  bool get forVideo => widget.videoId != null;

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
      if (forVideo) {
        final result = await widget.analytics.video(widget.videoId!, range);
        OwnedVideo? detail = owned;
        if (detail == null && widget.content != null) {
          try {
            detail = await widget.content!.ownedVideo(widget.videoId!);
          } catch (_) {
            // The header is optional chrome.
          }
        }
        if (mounted) {
          setState(() {
            video = result;
            owned = detail;
          });
        }
      } else {
        final result = await widget.analytics.creator(range);
        if (mounted) setState(() => creator = result);
      }
    } catch (failure) {
      if (mounted) setState(() => error = failure);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  void pick(String value) {
    if (range == value) return;
    range = value;
    load();
  }

  Widget chips() => Wrap(spacing: 8, runSpacing: 4, children: [
        for (final (label, value) in forVideo
            ? const [('7 days', '7d'), ('Since published', 'since_published')]
            : const [('7 days', '7d'), ('28 days', '28d')])
          ChoiceChip(
              label: Text(label),
              labelStyle: KoloVibeText.body(12,
                  weight: FontWeight.w600,
                  color: range == value ? Colors.white : KoloVibeColors.navy),
              selected: range == value,
              onSelected: loading ? null : (_) => pick(value)),
      ]);

  Widget metric(String label, String value, {double size = 26}) => Expanded(
        child: Semantics(
          container: true,
          label: '$label $value',
          excludeSemantics: true,
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(label, style: KoloVibeText.body(11)),
            const SizedBox(height: 5),
            Text(value, style: KoloVibeText.heading(size)),
          ]),
        ),
      );

  Widget card(Widget child) => Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(KoloVibeRadii.card)),
      child: child);

  /// M-060: nothing to show yet, or the service could not be read.
  Widget emptyState({required bool unavailable}) =>
      Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        card(Row(children: [
          metric('Qualified plays', '—'),
          const SizedBox(width: 12),
          metric('Watch time', '—'),
        ])),
        const SizedBox(height: 16),
        const KoloMedallion(KoloIcons.chartNoAxes),
        const SizedBox(height: 16),
        KoloHeadline(
            unavailable
                ? 'Analytics are\ntaking a moment.'
                : 'Every story starts somewhere.',
            size: 26),
        const SizedBox(height: 12),
        Text(
            unavailable
                ? 'We couldn’t read your analytics right now. Your originals and Lone Stars are not affected.'
                : 'Publish your first original to begin seeing qualified activity and watch-time insights here.',
            style: KoloVibeText.body(14, height: 1.5)),
        const SizedBox(height: 16),
        if (unavailable)
          FilledButton(onPressed: load, child: const Text('Try again'))
        else
          FilledButton(
              onPressed: () => openCreatorScreen(context, 41),
              child: const Text('Create your first video')),
        const SizedBox(height: 16),
        KoloNote(
            title: unavailable ? 'Metrics unavailable' : 'No data yet',
            message:
                'Unavailable metrics are shown as dashes, not zero performance. Activity appears when available.',
            asset: KoloIcons.info),
      ]);

  Widget creatorBody(CreatorAnalytics data) =>
      Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const KoloHeadline('Stories that connect.', size: 30),
        const SizedBox(height: 16),
        card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            metric('Qualified plays', analyticsCount(data.qualifiedPlays)),
            const SizedBox(width: 12),
            metric('Watch time', watchTime(data.watchTimeSeconds)),
          ]),
          const SizedBox(height: 16),
          AnalyticsChart(days: data.daily),
        ])),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(
              child: card(Row(
                  children: [metric('Likes', analyticsCount(data.likes))]))),
          const SizedBox(width: 12),
          Expanded(
              child: card(Row(children: [
            metric('New followers', analyticsCount(data.newFollowers))
          ]))),
        ]),
        const SizedBox(height: 16),
        Text(
            'Counts come from the engagement service and may be adjusted after validation. No earnings are shown.',
            style: KoloVibeText.body(11, height: 1.5)),
        if (data.top.isNotEmpty) ...[
          const SizedBox(height: 20),
          const KoloHeadline('Top original', size: 18),
          const SizedBox(height: 12),
          for (final original in data.top)
            Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: InkWell(
                    borderRadius: BorderRadius.circular(KoloVibeRadii.tile),
                    onTap: () => openCreatorScreen(context, 59,
                        entityId: original.videoId),
                    child: ConstrainedBox(
                        constraints: const BoxConstraints(minHeight: 48),
                        child: Row(children: [
                          Expanded(
                              child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                Text(original.title,
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                    style: KoloVibeText.body(14,
                                        weight: FontWeight.w600,
                                        color: KoloVibeColors.navy)),
                                Text(
                                    '${analyticsCount(original.qualifiedPlays)} qualified plays',
                                    style: KoloVibeText.body(11)),
                              ])),
                          const Icon(Icons.chevron_right,
                              color: KoloVibeColors.muted),
                        ])))),
        ],
      ]);

  Widget videoBody(VideoAnalytics data) =>
      Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        if (owned != null) ...[
          Row(children: [
            Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  Text(owned!.title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: KoloVibeText.body(14,
                          weight: FontWeight.w600, color: KoloVibeColors.navy)),
                  const SizedBox(height: 4),
                  KoloBadge(owned!.state == 'published'
                      ? 'Published'
                      : owned!.state[0].toUpperCase() +
                          owned!.state.substring(1)),
                ])),
          ]),
          const SizedBox(height: 16),
        ],
        chips(),
        const SizedBox(height: 16),
        card(Row(children: [
          metric('Qualified plays', analyticsCount(data.qualifiedPlays)),
          const SizedBox(width: 12),
          metric('Watch time', watchTime(data.watchTimeSeconds)),
        ])),
        const SizedBox(height: 12),
        Row(children: [
          metric('Likes', analyticsCount(data.likes)),
          const SizedBox(width: 12),
          metric('Shares', analyticsCount(data.shares)),
          const SizedBox(width: 12),
          metric('Avg. watch', clockTime(data.averageWatchSeconds)),
        ]),
        const SizedBox(height: 20),
        const KoloHeadline('Reading these numbers', size: 18),
        const SizedBox(height: 8),
        Text(
            'Plays and engagement are subject to validation. Watch-time values are estimates and may change as activity is processed.',
            style: KoloVibeText.body(12, height: 1.5)),
        const SizedBox(height: 8),
        Text('No revenue or payout figures are shown.',
            style: KoloVibeText.body(11, height: 1.5)),
      ]);

  Widget body() {
    if (loading) return const SystemLoading();
    final failure = error;
    if (failure != null) {
      final status = failure is ApiFailure ? failure.status : null;
      // 403/404/503 are normal states for a capability that may be closed.
      if (status == 403 || status == 404 || status == 503) {
        return emptyState(unavailable: true);
      }
      return SystemFailureView(
          error: failure,
          onRetry: load,
          onSignIn: () => signInThenReturn(context, forVideo ? 59 : 58));
    }
    if (forVideo) {
      final data = video!;
      return data.empty && data.watchTimeSeconds == 0
          ? emptyState(unavailable: false)
          : videoBody(data);
    }
    final data = creator!;
    return data.empty ? emptyState(unavailable: false) : creatorBody(data);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
            title: Text(forVideo ? 'Video analytics' : 'Creator analytics')),
        body: SafeArea(
            child: RefreshIndicator(
          onRefresh: load,
          child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
              children: [
                if (!forVideo &&
                    !loading &&
                    error == null &&
                    creator != null &&
                    !creator!.empty) ...[
                  chips(),
                  const SizedBox(height: 16),
                ],
                body(),
              ]),
        )),
        bottomNavigationBar:
            creatorNavigation(context, widget.catalog, forVideo ? 59 : 58),
      );
}

/// Daily qualified plays as bars; the three most recent days are red, as drawn.
class AnalyticsChart extends StatelessWidget {
  const AnalyticsChart({super.key, required this.days});
  final List<AnalyticsDay> days;

  @override
  Widget build(BuildContext context) {
    if (days.isEmpty) return const SizedBox.shrink();
    final first = days.first.date, last = days.last.date;
    final middle = days[days.length ~/ 2].date;
    return Semantics(
      label:
          'Qualified plays per day, ${chartDate(first)} to ${chartDate(last)}',
      child: Column(children: [
        SizedBox(
            height: 120,
            width: double.infinity,
            child: ExcludeSemantics(
                child: CustomPaint(painter: _BarPainter(days)))),
        const SizedBox(height: 8),
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          for (final date in [first, middle, last])
            Text(chartDate(date), style: KoloVibeText.body(9)),
        ]),
      ]),
    );
  }
}

class _BarPainter extends CustomPainter {
  _BarPainter(this.days);
  final List<AnalyticsDay> days;

  @override
  void paint(Canvas canvas, Size size) {
    final peak = days.fold<int>(
        1, (m, d) => d.qualifiedPlays > m ? d.qualifiedPlays : m);
    final gap = 4.0;
    final width = (size.width - gap * (days.length - 1)) / days.length;
    for (var i = 0; i < days.length; i++) {
      final height = days[i].qualifiedPlays == 0
          ? 2.0
          : (size.height * days[i].qualifiedPlays / peak)
              .clamp(2.0, size.height);
      final recent = i >= days.length - 3;
      canvas.drawRRect(
          RRect.fromRectAndRadius(
              Rect.fromLTWH(
                  i * (width + gap), size.height - height, width, height),
              const Radius.circular(3)),
          Paint()
            ..color = recent ? KoloVibeColors.red : const Color(0xFFD8E2F8));
    }
  }

  @override
  bool shouldRepaint(_BarPainter old) => old.days != days;
}
