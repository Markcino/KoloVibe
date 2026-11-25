import 'package:flutter/material.dart';
import '../../core/network/api_client.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/state/async_resource.dart';
import '../../shared/widgets/kolo_components.dart';
import 'live_restriction_repository.dart';

/// Decision F (D-8): the creator's own measures on the account status screen
/// (M-077), with an appeal for an active measure.
///
/// These states follow the existing account status components. They are not
/// in an approved design export and are NOT visually approved until the owner
/// reviews them. Whether a measure is active or may be appealed is the
/// server's answer; the server also enforces ownership and one appeal per
/// measure. A failure here never hides the rest of the account status.
class MeasuresSection extends StatefulWidget {
  const MeasuresSection({super.key, required this.repository});
  final LiveRestrictionRepository repository;

  @override
  State<MeasuresSection> createState() => _MeasuresSectionState();
}

class _MeasuresSectionState extends State<MeasuresSection> {
  late final AsyncResource<OwnMeasures> measures = AsyncResource(
      widget.repository.mine,
      unreadable: 'Your account measures could not be read. Try again.')
    ..load();

  @override
  void dispose() {
    measures.dispose();
    super.dispose();
  }

  Future<void> _appeal(CreatorMeasure measure) async {
    final sent = await showModalBottomSheet<bool>(
        context: context,
        isScrollControlled: true,
        builder: (context) =>
            _AppealSheet(measure: measure, repository: widget.repository));
    if (sent == true && mounted) await measures.load();
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
      listenable: measures,
      builder: (context, _) =>
          Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            const SizedBox(height: 16),
            Semantics(
                header: true,
                child: const KoloHeadline('Account measures', size: 18)),
            ..._content(context),
          ]));

  List<Widget> _content(BuildContext context) {
    switch (measures.phase) {
      case ResourcePhase.loading:
        return const [
          ListTile(
              leading: SizedBox.square(
                  dimension: 20,
                  child: CircularProgressIndicator(strokeWidth: 2)),
              title: Text('Loading account measures'))
        ];
      case ResourcePhase.failed:
        return [
          const ListTile(title: Text('Account measures are unavailable.')),
          Align(
              alignment: Alignment.centerLeft,
              child: TextButton(
                  onPressed: measures.load, child: const Text('Try again'))),
        ];
      case ResourcePhase.ready:
        final items = measures.value!.items;
        if (items.isEmpty) {
          return const [ListTile(title: Text('No measures on your account.'))];
        }
        return [for (final item in items) _card(context, item)];
    }
  }

  Widget _card(BuildContext context, CreatorMeasure measure) {
    final local = MaterialLocalizations.of(context);
    String day(DateTime value) => local.formatMediumDate(value.toLocal());
    final state = measure.active
        ? (measure.expiresAt == null
            ? 'Active'
            : 'Active until ${day(measure.expiresAt!)}')
        : (measure.liftedAt != null
            ? 'Lifted ${day(measure.liftedAt!)}'
            : 'Ended');
    return Card(
        child: Padding(
            padding: const EdgeInsets.all(16),
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(measureKindLabel(measure.kind),
                  style: KoloVibeText.body(15,
                      weight: FontWeight.w600, color: KoloVibeColors.navy)),
              const SizedBox(height: 4),
              Text('$state · issued ${day(measure.issuedAt)}',
                  style: KoloVibeText.body(12, color: KoloVibeColors.muted)),
              if (measure.active) ...[
                const SizedBox(height: 8),
                Text(measureKindEffect(measure.kind),
                    style: KoloVibeText.body(14, height: 1.4)),
              ],
              const SizedBox(height: 8),
              Text(
                  'Reason code ${measure.reasonCode} · policy ${measure.policyVersion}',
                  style: KoloVibeText.body(12, color: KoloVibeColors.muted)),
              if (measure.appeal != null) ...[
                const SizedBox(height: 8),
                Text(measureAppealLabel(measure.appeal!.status),
                    style: KoloVibeText.body(13, weight: FontWeight.w600)),
              ],
              if (measure.appealable) ...[
                const SizedBox(height: 8),
                OutlinedButton(
                    onPressed: () => _appeal(measure),
                    child: const Text('Appeal this measure')),
              ],
            ])));
  }
}

class _AppealSheet extends StatefulWidget {
  const _AppealSheet({required this.measure, required this.repository});
  final CreatorMeasure measure;
  final LiveRestrictionRepository repository;

  @override
  State<_AppealSheet> createState() => _AppealSheetState();
}

class _AppealSheetState extends State<_AppealSheet> {
  final statement = TextEditingController();
  final form = GlobalKey<FormState>();
  bool sending = false;
  String? failure;

  @override
  void dispose() {
    statement.dispose();
    super.dispose();
  }

  String _failureText(Object error) {
    if (error is ApiFailure) {
      if (error.status == 409) {
        return 'This measure already has an appeal, or it no longer applies.';
      }
      if (error.status == 404) return 'This measure is no longer available.';
      if (error.kind == FailureKind.offline) {
        return 'Check your connection, then try again. Your statement is kept.';
      }
      if (error.status == 401) return 'Sign in again to send your appeal.';
    }
    return 'Your appeal could not be sent. Your statement is kept. Try again.';
  }

  Future<void> _send() async {
    if (sending || !(form.currentState?.validate() ?? false)) return;
    setState(() {
      sending = true;
      failure = null;
    });
    try {
      await widget.repository
          .appeal(measureId: widget.measure.id, reason: statement.text);
      if (mounted) Navigator.of(context).pop(true);
    } catch (error) {
      if (mounted) setState(() => failure = _failureText(error));
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }

  @override
  Widget build(BuildContext context) => Padding(
      padding: EdgeInsets.fromLTRB(
          24, 24, 24, 24 + MediaQuery.viewInsetsOf(context).bottom),
      child: Form(
          key: form,
          child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Semantics(
                    header: true,
                    child: KoloHeadline(
                        'Appeal: ${measureKindLabel(widget.measure.kind)}',
                        size: 20)),
                const SizedBox(height: 8),
                Text(
                    'An administrator who did not issue this measure will read your statement.',
                    style: KoloVibeText.body(14, height: 1.5)),
                const SizedBox(height: 16),
                TextFormField(
                    controller: statement,
                    minLines: 3,
                    maxLines: 6,
                    maxLength: 2000,
                    enabled: !sending,
                    decoration:
                        const InputDecoration(labelText: 'Your statement'),
                    validator: (value) => (value ?? '').trim().length < 10
                        ? 'Write at least 10 characters.'
                        : null),
                if (failure != null)
                  KoloNote(
                      title: 'Not sent',
                      message: failure!,
                      tone: KoloNoteTone.alert),
                const SizedBox(height: 8),
                FilledButton(
                    onPressed: sending ? null : _send,
                    child: Text(sending ? 'Sending…' : 'Send appeal')),
              ])));
}
