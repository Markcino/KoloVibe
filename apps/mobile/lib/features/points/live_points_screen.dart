import 'package:flutter/material.dart';
import '../../shared/widgets/kolo_components.dart';

import '../../app/screen_route.dart';
import '../../core/presentation/design_node.dart';
import '../../shared/widgets/live_state_view.dart';
import '../creators/creator_shell.dart';
import 'live_points_repository.dart';
import 'points_controller.dart';
import 'points_widgets.dart';

/// Lone Stars (M-061–M-069): the creator's server-owned, non-cash ledger.
///
/// Read-only. The app never awards, adjusts or computes points, and shows no
/// figure the gateway did not return.
class LivePointsScreen extends StatelessWidget {
  const LivePointsScreen(
      {super.key,
      required this.route,
      required this.catalog,
      required this.repository,
      this.videoTitle});
  final ScreenRoute route;
  final DesignCatalog catalog;
  final LivePointsRepository repository;

  /// Optional: resolves a source video id to its public title (M-065).
  final Future<String?> Function(String videoId)? videoTitle;

  @override
  Widget build(BuildContext context) => switch (route.screen) {
        65 => LivePointsEntryScreen(
            route: route,
            catalog: catalog,
            repository: repository,
            videoTitle: videoTitle),
        68 => LivePointsRulesScreen(catalog: catalog),
        _ => LivePointsLedgerScreen(
            route: route,
            catalog: catalog,
            view: viewFor(route.screen),
            repository: repository),
      };

  /// The ledger slice each route shows (61 and 69 are the overview).
  static PointsView viewFor(int screen) => switch (screen) {
        62 => PointsView.confirmed,
        63 => PointsView.pending,
        64 => PointsView.history,
        66 => PointsView.withheld,
        67 => PointsView.adjustments,
        _ => PointsView.overview,
      };
}

/// Overview, confirmed, pending, history, withheld and adjustments lists.
class LivePointsLedgerScreen extends StatefulWidget {
  const LivePointsLedgerScreen(
      {super.key,
      required this.route,
      required this.catalog,
      required this.view,
      required this.repository,
      this.controller});
  final ScreenRoute route;
  final DesignCatalog catalog;
  final PointsView view;
  final LivePointsRepository repository;

  /// Test seam for a pre-built controller.
  final PointsController? controller;

  @override
  State<LivePointsLedgerScreen> createState() => _LivePointsLedgerScreenState();
}

class _LivePointsLedgerScreenState extends State<LivePointsLedgerScreen> {
  late final PointsController controller;

  @override
  void initState() {
    super.initState();
    controller =
        widget.controller ?? PointsController(widget.repository, widget.view);
    controller.load();
  }

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  int get screen => widget.route.screen;

  void _open(int target, {String? entityId}) =>
      openCreatorScreen(context, target, entityId: entityId);

  void _openEntry(PointsEntry entry) => _open(65, entityId: entry.id);

  String get _title {
    switch (widget.view) {
      case PointsView.overview:
        final empty =
            controller.phase == PointsPhase.ready && !controller.hasAnyEntries;
        return screen == 69 && empty ? 'No points activity' : 'Lone Stars';
      case PointsView.confirmed:
        return 'Confirmed Lone Stars';
      case PointsView.pending:
        return 'Pending Lone Stars';
      case PointsView.history:
        return 'Transaction history';
      case PointsView.withheld:
        return 'Withheld points';
      case PointsView.adjustments:
        return 'Reversed points';
    }
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: controller,
        builder: (context, _) => Scaffold(
          appBar: AppBar(title: Text(_title)),
          body: SafeArea(child: _body(context)),
          bottomNavigationBar:
              creatorNavigation(context, widget.catalog, screen),
        ),
      );

  Widget _body(BuildContext context) {
    switch (controller.phase) {
      case PointsPhase.loading:
        return const LiveStateView.loading(label: 'Loading your Lone Stars');
      case PointsPhase.failed:
        return pointsFailureView(context, controller.error!,
            onRetry: controller.load,
            onSignIn: () => signInThenReturn(context, screen),
            onStudio: () => _open(37));
      case PointsPhase.ready:
        return RefreshIndicator(
          onRefresh: controller.refresh,
          child: ListView(
              padding: const EdgeInsets.all(16),
              physics: const AlwaysScrollableScrollPhysics(),
              children: [
                if (controller.refreshError != null) _refreshBanner(context),
                ..._content(context),
              ]),
        );
    }
  }

  Widget _refreshBanner(BuildContext context) => Card(
        child: ListTile(
          leading: const Icon(Icons.wifi_off),
          title: const Text('Could not refresh'),
          subtitle: const Text('Showing the Lone Stars you last loaded.'),
          trailing: TextButton(
              onPressed: controller.refresh, child: const Text('Try again')),
        ),
      );

  List<Widget> _content(BuildContext context) {
    final balance = controller.balance!;
    final text = Theme.of(context).textTheme;
    switch (widget.view) {
      case PointsView.overview:
        return _overview(context, balance);
      case PointsView.confirmed:
        return [
          Text('Confirmed Lone Stars', style: text.titleMedium),
          Text(formatPoints(balance.balance), style: text.displayMedium),
          const Text('Confirmed recognition points'),
          const SizedBox(height: 8),
          const PointsNote(
              'These points have completed the current qualification checks. They are non-cash recognition, not a spendable balance.'),
          ..._rows(context,
              empty: 'No confirmed Lone Stars yet. Qualified activity will '
                  'appear here once it is confirmed.'),
          ..._footer(),
          TextButton(
              onPressed: () => _open(64),
              child: const Text('View points history')),
        ];
      case PointsView.pending:
        return [
          Text('Pending Lone Stars', style: text.titleMedium),
          Text(formatPoints(balance.pending), style: text.displayMedium),
          const Text('Recognition points awaiting qualification'),
          const SizedBox(height: 8),
          const PointsNote(
              'Pending activity is still being checked and may be confirmed, withheld or adjusted. It is not guaranteed recognition.'),
          ..._rows(context, empty: 'Nothing is being checked right now.'),
          ..._footer(),
          const PointsNote(
              'No processing time is promised. Check status here when it changes.'),
          TextButton(
              onPressed: () => _open(68),
              child: const Text('Read eligibility rules')),
        ];
      case PointsView.history:
        return [
          Text('Lone Stars · Non-cash points ledger', style: text.titleMedium),
          const SizedBox(height: 8),
          Wrap(spacing: 8, children: [
            for (final (label, value) in const [
              ('All', PointsFilter.all),
              ('Confirmed', PointsFilter.confirmed),
              ('Pending', PointsFilter.pending),
              ('Adjustments', PointsFilter.adjustments),
            ])
              ChoiceChip(
                  label: Text(label),
                  selected: controller.filter == value,
                  onSelected: (_) => controller.setFilter(value)),
          ]),
          ..._rows(context, empty: 'No activity for this filter yet.'),
          ..._footer(),
          const SizedBox(height: 8),
          const Text('Recognition activity, not financial transactions.'),
        ];
      case PointsView.withheld:
        return [
          KoloHeroStat(
              icon: Icons.shield_outlined,
              value: '${formatPoints(balance.withheld)} withheld',
              caption: 'Excluded from confirmed recognition'),
          const PointsNote(
              'Some interaction patterns were not eligible under the current recognition rules. Details are limited to protect anti-abuse checks.'),
          ..._rows(context, empty: 'No withheld activity found.'),
          ..._footer(),
          const PointsNote(
              'Withheld points are not part of your confirmed Lone Stars. This is a non-cash status, not a money deduction.'),
          TextButton(
              onPressed: () => _open(68),
              child: const Text('Review eligibility rules')),
        ];
      case PointsView.adjustments:
        return [
          KoloHeroStat(
              icon: Icons.history,
              value: '${formatPoints(balance.reversed)} reversed',
              caption: 'Recognition adjustments'),
          const PointsNote(
              'A later activity review found that previously counted recognition did not qualify. The confirmed total reflects these adjustments.'),
          ..._rows(context, empty: 'No adjustments to your Lone Stars.'),
          ..._footer(),
          const PointsNote(
              'Lone Stars are non-cash. An adjustment is not a payment, charge or financial penalty.'),
          TextButton(
              onPressed: () => _open(64),
              child: const Text('View related history')),
          TextButton(
              onPressed: () => _open(68),
              child: const Text('Read recognition rules')),
        ];
    }
  }

  List<Widget> _overview(BuildContext context, PointsBalance balance) {
    final text = Theme.of(context).textTheme;
    if (!controller.hasAnyEntries) {
      // M-069: the ledger is empty. Show the server's totals, no samples.
      return [
        const KoloHeroStat(
            dark: true,
            value: 'Your story starts here.',
            caption: 'No Lone Stars activity yet'),
        const Text(
            'Keep creating original work and building genuine community connections. Eligible recognition will appear here when available.'),
        const SizedBox(height: 8),
        const PointsNote(
            'Lone Stars are non-cash points. Activity does not guarantee an award.'),
        FilledButton(
            onPressed: () => _open(37),
            child: const Text('Visit Creator Studio')),
        TextButton(
            onPressed: () => _open(68),
            child: const Text('How Lone Stars work')),
      ];
    }
    final recent = controller.entries.take(5).toList();
    return [
      Text('COMMUNITY RECOGNITION', style: text.labelMedium),
      Text(formatPoints(balance.balance), style: text.displayMedium),
      InkWell(
          onTap: () => _open(62),
          child: Text('Confirmed Lone Stars', style: text.titleMedium)),
      const Text('Non-cash recognition. Not money or redeemable value.'),
      const SizedBox(height: 8),
      PointsStatTile(
          label: 'Pending', value: balance.pending, onTap: () => _open(63)),
      PointsStatTile(
          label: 'Withheld', value: balance.withheld, onTap: () => _open(66)),
      if (balance.reversed > 0)
        PointsStatTile(
            label: 'Reversed', value: balance.reversed, onTap: () => _open(67)),
      const SizedBox(height: 16),
      Text('Recent recognition', style: text.titleMedium),
      for (final entry in recent)
        PointsEntryTile(entry: entry, onTap: () => _openEntry(entry)),
      TextButton(onPressed: () => _open(64), child: const Text('History')),
      TextButton(
          onPressed: () => _open(68),
          child: const Text('How recognition works')),
    ];
  }

  List<Widget> _rows(BuildContext context, {required String empty}) {
    final rows = controller.entries;
    return [
      const SizedBox(height: 8),
      if (rows.isEmpty && !controller.hasMore && !controller.loadingMore)
        ListTile(title: Text(empty)),
      for (final entry in rows)
        PointsEntryTile(entry: entry, onTap: () => _openEntry(entry)),
    ];
  }

  /// Paging footer: progress, an inline retry that keeps the rows, or a
  /// "Load more" button while the server has another page.
  List<Widget> _footer() {
    if (controller.loadingMore) {
      return [
        const Padding(
            padding: EdgeInsets.all(16),
            child: Center(child: CircularProgressIndicator()))
      ];
    }
    if (controller.moreError != null) {
      return [
        Semantics(
            liveRegion: true,
            child: const ListTile(
                leading: Icon(Icons.error_outline),
                title: Text('Could not load more activity'))),
        TextButton(
            onPressed: controller.loadMore, child: const Text('Try again')),
      ];
    }
    if (controller.hasMore) {
      return [
        TextButton(
            onPressed: controller.loadMore,
            child: Text(
                widget.view == PointsView.withheld && controller.entries.isEmpty
                    ? 'Check older activity'
                    : 'Load more')),
      ];
    }
    return const [];
  }
}

/// M-065: one owner-only ledger entry.
class LivePointsEntryScreen extends StatefulWidget {
  const LivePointsEntryScreen(
      {super.key,
      required this.route,
      required this.catalog,
      required this.repository,
      this.videoTitle,
      this.controller});
  final ScreenRoute route;
  final DesignCatalog catalog;
  final LivePointsRepository repository;
  final Future<String?> Function(String videoId)? videoTitle;
  final PointsEntryController? controller;

  @override
  State<LivePointsEntryScreen> createState() => _LivePointsEntryScreenState();
}

class _LivePointsEntryScreenState extends State<LivePointsEntryScreen> {
  PointsEntryController? controller;

  @override
  void initState() {
    super.initState();
    final id = widget.route.entityId;
    controller = widget.controller ??
        (id == null
            ? null
            : PointsEntryController(widget.repository, id,
                videoTitle: widget.videoTitle));
    controller?.load();
  }

  @override
  void dispose() {
    controller?.dispose();
    super.dispose();
  }

  void _history() {
    if (Navigator.of(context).canPop()) {
      Navigator.of(context).pop();
    } else {
      openCreatorScreen(context, 64);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Transaction details')),
        body: SafeArea(child: _body(context)),
        bottomNavigationBar: creatorNavigation(context, widget.catalog, 65),
      );

  Widget _body(BuildContext context) {
    final controller = this.controller;
    if (controller == null) {
      return LiveStateView.empty(
          title: 'Choose an entry',
          message: 'Open an entry from your Lone Stars history to see it here.',
          actionLabel: 'View points history',
          onAction: () => openCreatorScreen(context, 64));
    }
    return ListenableBuilder(
        listenable: controller,
        builder: (context, _) {
          switch (controller.phase) {
            case PointsEntryPhase.loading:
              return const LiveStateView.loading(label: 'Loading this entry');
            case PointsEntryPhase.failed:
              return pointsFailureView(context, controller.error!,
                  onRetry: controller.load,
                  onSignIn: () => signInThenReturn(context, 64),
                  onStudio: () => openCreatorScreen(context, 37));
            case PointsEntryPhase.ready:
              return _detail(context, controller);
          }
        });
  }

  Widget _detail(BuildContext context, PointsEntryController controller) {
    final entry = controller.entry!;
    final local = MaterialLocalizations.of(context);
    return RefreshIndicator(
      onRefresh: controller.load,
      child: ListView(
          padding: const EdgeInsets.all(16),
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            KoloHeroStat(
                dark: true,
                value: '${entryAmount(entry)} Lone Stars',
                caption: '${entryStatusLabel(entry)} · ${entryTitle(entry)}'),
            if (entry.videoId != null)
              ListTile(
                  title: const Text('Source'),
                  subtitle: Text(controller.sourceTitle ??
                      'Video details are unavailable')),
            ListTile(
                title: const Text('Recorded'),
                subtitle:
                    Text(local.formatFullDate(entry.createdAt.toLocal()))),
            ListTile(
                title: const Text('Activity status'),
                subtitle: Text(_statusText(entry))),
            const PointsNote(
                'Recognition only. This entry has no cash value, exchange rate or withdrawal option.'),
            if (entry.isWithheld) ...[
              const PointsNote(
                  'Withheld points are not part of your confirmed Lone Stars. Details are limited to protect anti-abuse checks.'),
              TextButton(
                  onPressed: () => openCreatorScreen(context, 66),
                  child: const Text('Review withheld points')),
            ],
            if (entry.isReversal) ...[
              const PointsNote(
                  'A later activity review found that previously counted recognition did not qualify. This adjustment is not a payment, charge or financial penalty.'),
              TextButton(
                  onPressed: () => openCreatorScreen(context, 67),
                  child: const Text('View reversed points')),
            ],
            FilledButton(
                onPressed: _history, child: const Text('Back to history')),
          ]),
    );
  }

  String _statusText(PointsEntry entry) {
    if (entry.isPending) return 'This activity is still being checked';
    if (entry.isWithheld) return 'The activity didn’t meet eligibility checks';
    if (entry.kind == 'award') return 'Qualification checks completed';
    return 'A recognition adjustment was recorded';
  }
}

/// M-068: how recognition works. Static approved guidance; no account data.
class LivePointsRulesScreen extends StatelessWidget {
  const LivePointsRulesScreen({super.key, required this.catalog});
  final DesignCatalog catalog;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Engagement eligibility')),
      body: SafeArea(
          child: ListView(padding: const EdgeInsets.all(16), children: [
        Text('Real connection. Real recognition.', style: text.headlineMedium),
        const SizedBox(height: 8),
        const Text(
            'Lone Stars recognise eligible community activity under the current platform rules.'),
        const SizedBox(height: 16),
        const _Rule('Keep it genuine',
            'Authentic interactions, not artificial engagement.'),
        const _Rule('Respect original work',
            'Follow content rights and community guidelines.'),
        const _Rule('What doesn’t qualify',
            'Spam, manipulated activity and ineligible interactions can be excluded or reversed.'),
        const _Rule('Not a rewards currency',
            'No cash value, ad-viewing rewards, conversion formula or guaranteed points per action.'),
        const SizedBox(height: 8),
        FilledButton(
            onPressed: () => Navigator.of(context).canPop()
                ? Navigator.of(context).pop()
                : openCreatorScreen(context, 61),
            child: const Text('Back to Lone Stars')),
      ])),
      bottomNavigationBar: creatorNavigation(context, catalog, 68),
    );
  }
}

class _Rule extends StatelessWidget {
  const _Rule(this.title, this.body);
  final String title, body;

  @override
  Widget build(BuildContext context) =>
      Card(child: ListTile(title: Text(title), subtitle: Text(body)));
}
