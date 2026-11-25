import 'package:flutter/material.dart';

import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/kolo_components.dart';
import '../system/system_ui.dart';
import 'live_legal_repository.dart';

/// The pending-review note shown with every draft text (Decision B). Never hidden while the status is pending.
class LegalReviewNote extends StatelessWidget {
  const LegalReviewNote({super.key});
  @override
  Widget build(BuildContext context) => const KoloNote(
      key: ValueKey('legal-pending-review'),
      title: 'Draft pending legal review',
      message:
          'This text has not been approved by a lawyer yet. It describes how KoloVibe works today and may change. You will be asked to accept any new version.',
      icon: Icons.gavel_outlined);
}

/// Renders the small Markdown subset the legal texts use: `#` and `##` headings, `-` lists, `**bold**` runs.
class LegalText extends StatelessWidget {
  const LegalText(this.text, {super.key});
  final String text;

  static List<InlineSpan> _inline(String line) {
    final spans = <InlineSpan>[];
    final parts = line.split('**');
    for (final (index, part) in parts.indexed) {
      if (part.isEmpty) continue;
      spans.add(TextSpan(
          text: part,
          style: index.isOdd
              ? const TextStyle(fontWeight: FontWeight.w700)
              : null));
    }
    return spans;
  }

  @override
  Widget build(BuildContext context) {
    final body = Theme.of(context).textTheme.bodyMedium;
    final blocks = <Widget>[];
    for (final raw in text.split('\n')) {
      final line = raw.trimRight();
      if (line.isEmpty) continue;
      if (line.startsWith('# ')) {
        blocks.add(Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: KoloHeadline(line.substring(2), size: 24)));
      } else if (line.startsWith('## ')) {
        blocks.add(Padding(
            padding: const EdgeInsets.only(top: 12, bottom: 6),
            child: Text(line.substring(3),
                style: KoloVibeText.body(16, height: 1.3)
                    .copyWith(fontWeight: FontWeight.w700))));
      } else if (line.startsWith('- ')) {
        blocks.add(Padding(
            padding: const EdgeInsets.only(left: 8, bottom: 6),
            child: Text.rich(
                TextSpan(children: [
                  const TextSpan(text: '•  '),
                  ..._inline(line.substring(2))
                ]),
                style: body)));
      } else {
        blocks.add(Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Text.rich(TextSpan(children: _inline(line)), style: body)));
      }
    }
    return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch, children: blocks);
  }
}

/// Reads the current text of one document from the service, readable before registration.
class LegalDocumentScreen extends StatefulWidget {
  const LegalDocumentScreen(
      {super.key, required this.repository, required this.kind});
  final LiveLegalRepository repository;
  final String kind;
  @override
  State<LegalDocumentScreen> createState() => _LegalDocumentScreenState();
}

class _LegalDocumentScreenState extends State<LegalDocumentScreen> {
  LegalDocument? document;
  Object? error;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    setState(() => error = null);
    try {
      final value = await widget.repository.document(widget.kind);
      if (mounted) setState(() => document = value);
    } catch (failure) {
      if (mounted) setState(() => error = failure);
    }
  }

  @override
  Widget build(BuildContext context) {
    final current = document;
    return Scaffold(
      appBar: AppBar(title: Text(current?.summary.title ?? 'KoloVibe')),
      body: SafeArea(
        child: error != null
            ? SystemFailureView(error: error!, onRetry: load)
            : current == null
                ? const SystemLoading()
                : ListView(
                    key: ValueKey('legal-${widget.kind}'),
                    padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
                    children: [
                      if (current.summary.pendingLegalReview) ...[
                        const LegalReviewNote(),
                        const SizedBox(height: 16),
                      ],
                      Text(
                          'Version ${current.summary.version} · effective ${current.summary.effectiveAt}',
                          key: const ValueKey('legal-version')),
                      const SizedBox(height: 16),
                      LegalText(current.text),
                    ],
                  ),
      ),
    );
  }
}

void openLegalDocument(
    BuildContext context, LiveLegalRepository repository, String kind) {
  Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => LegalDocumentScreen(repository: repository, kind: kind)));
}

/// Shown after sign-in when a newer version of the terms or the privacy notice has not been accepted. Privacy
/// requests and signing out stay reachable: the person is never trapped behind it.
class LegalAcceptanceScreen extends StatefulWidget {
  const LegalAcceptanceScreen({
    super.key,
    required this.repository,
    required this.state,
    required this.onAccepted,
    required this.onSignOut,
    required this.onPrivacy,
  });
  final LiveLegalRepository repository;
  final LegalState state;
  final ValueChanged<LegalState> onAccepted;
  final VoidCallback onSignOut, onPrivacy;
  @override
  State<LegalAcceptanceScreen> createState() => _LegalAcceptanceScreenState();
}

class _LegalAcceptanceScreenState extends State<LegalAcceptanceScreen> {
  late LegalState state = widget.state;
  bool agreed = false, busy = false;
  Object? error;

  /// Both required documents are offered together; Identity records only the ones not yet accepted as they stand.
  List<LegalRecord> get pending => state.documents;

  Future<void> accept() async {
    if (busy || !agreed) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final next = await widget.repository.accept({
        for (final record in pending)
          record.summary.kind: record.summary.version
      });
      if (!mounted) return;
      if (next.acceptanceRequired) {
        setState(() {
          state = next;
          agreed = false;
        });
      } else {
        widget.onAccepted(next);
      }
    } catch (failure) {
      if (!mounted) return;
      if (isOutdatedLegalVersion(failure)) {
        // The text changed while this screen was open: show the new version and ask again.
        try {
          final fresh = await widget.repository.state();
          if (mounted) setState(() => state = fresh);
        } catch (_) {}
        if (mounted) {
          setState(() {
            agreed = false;
            error =
                'A newer version was just published. Read it, then accept again.';
          });
        }
      } else {
        setState(() => error = failure);
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        body: SafeArea(
          child: ListView(
            key: const ValueKey('legal-acceptance'),
            padding: const EdgeInsets.fromLTRB(20, 24, 20, 32),
            children: [
              const KoloHeadline('We have updated our terms', size: 26),
              const SizedBox(height: 12),
              const Text(
                  'Please read and accept the current version to keep using KoloVibe.'),
              const SizedBox(height: 16),
              if (state.documents.any((r) => r.summary.pendingLegalReview)) ...[
                const LegalReviewNote(),
                const SizedBox(height: 16),
              ],
              for (final record in pending)
                KoloListRow(
                    key: ValueKey('legal-read-${record.summary.kind}'),
                    title: 'Read the ${record.summary.title}',
                    subtitle: 'Version ${record.summary.version}',
                    icon: Icons.description_outlined,
                    onTap: () => openLegalDocument(
                        context, widget.repository, record.summary.kind)),
              CheckboxListTile(
                key: const ValueKey('legal-agree'),
                value: agreed,
                contentPadding: EdgeInsets.zero,
                controlAffinity: ListTileControlAffinity.leading,
                onChanged:
                    busy ? null : (v) => setState(() => agreed = v ?? false),
                title: Text(
                    'I accept the ${pending.map((r) => r.summary.title).join(' and the ')}.',
                    style: KoloVibeText.body(13, height: 1.4)),
              ),
              if (error != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Text(
                      error is String
                          ? error as String
                          : 'This could not be saved. Try again.',
                      key: const ValueKey('legal-error'),
                      style: TextStyle(
                          color: Theme.of(context).colorScheme.error)),
                ),
              FilledButton(
                  key: const ValueKey('legal-accept'),
                  onPressed: agreed && !busy ? accept : null,
                  child: const Text('Accept and continue')),
              const SizedBox(height: 8),
              TextButton(
                  onPressed: widget.onPrivacy,
                  child: const Text('Privacy settings and requests')),
              TextButton(
                  onPressed: widget.onSignOut, child: const Text('Sign out')),
            ],
          ),
        ),
      );
}

/// Remembers, per signed-in account and app run, whether the current versions are accepted, so the check runs
/// once per account rather than on every screen. A failed check never blocks: it is simply tried again later.
class LegalGateController {
  LegalGateController(this.repository);
  final LiveLegalRepository repository;
  final Map<String, Future<LegalState?>> _checks = {};
  final Set<String> _accepted = {};

  bool isAccepted(String accountId) => _accepted.contains(accountId);

  Future<LegalState?> check(String accountId) =>
      _checks.putIfAbsent(accountId, () async {
        try {
          final state = await repository.state();
          if (!state.acceptanceRequired) _accepted.add(accountId);
          return state;
        } catch (_) {
          _checks.remove(accountId);
          return null;
        }
      });

  void markAccepted(String accountId) {
    _accepted.add(accountId);
    _checks[accountId] = Future.value(null);
  }
}

/// Decision B, as the owner chose: the app asks for re-acceptance after sign-in; the API does not block. Privacy,
/// legal and sign-out screens are never gated, so privacy rights stay reachable.
class LegalAcceptanceGate extends StatefulWidget {
  const LegalAcceptanceGate({
    super.key,
    required this.controller,
    required this.accountId,
    required this.child,
    required this.onSignOut,
    required this.onPrivacy,
  });
  final LegalGateController controller;
  final String accountId;
  final Widget child;
  final VoidCallback onSignOut, onPrivacy;

  static const exemptScreens = {84, 85, 88, 90, 91, 92, 93, 94};

  @override
  State<LegalAcceptanceGate> createState() => _LegalAcceptanceGateState();
}

class _LegalAcceptanceGateState extends State<LegalAcceptanceGate> {
  late Future<LegalState?> check = widget.controller.check(widget.accountId);

  @override
  Widget build(BuildContext context) {
    if (widget.controller.isAccepted(widget.accountId)) return widget.child;
    return FutureBuilder<LegalState?>(
      future: check,
      builder: (context, snapshot) {
        final state = snapshot.data;
        if (state == null || !state.acceptanceRequired) return widget.child;
        return LegalAcceptanceScreen(
          repository: widget.controller.repository,
          state: state,
          onAccepted: (_) =>
              setState(() => widget.controller.markAccepted(widget.accountId)),
          onSignOut: widget.onSignOut,
          onPrivacy: widget.onPrivacy,
        );
      },
    );
  }
}
