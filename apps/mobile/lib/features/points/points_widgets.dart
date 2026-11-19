import 'package:flutter/material.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../core/network/api_client.dart';
import '../../shared/widgets/live_state_view.dart';
import 'live_points_repository.dart';

/// Display helpers for Lone Stars. These only format values the server sent.

/// 1240 -> "1,240". Negative values keep a true minus sign.
String formatPoints(int value) {
  final digits = value.abs().toString();
  final grouped =
      digits.replaceAllMapped(RegExp(r'\B(?=(\d{3})+(?!\d))'), (match) => ',');
  return value < 0 ? '−$grouped' : grouped;
}

/// An entry amount with an explicit sign: "+120" or "−20".
String signedPoints(int value) =>
    value > 0 ? '+${formatPoints(value)}' : formatPoints(value);

/// What an entry is, in the approved Lone Stars wording.
String entryTitle(PointsEntry entry) {
  if (entry.status == 'pending') return 'Activity being checked';
  if (entry.status == 'withheld') return 'Excluded activity';
  if (entry.kind == 'award') return 'Qualified engagement';
  return 'Recognition adjustment';
}

/// The state label shown beside an entry.
String entryStatusLabel(PointsEntry entry) {
  if (entry.status == 'pending') return 'Pending';
  if (entry.status == 'withheld') return 'Withheld';
  if (entry.kind == 'reversal') return 'Reversed';
  if (entry.kind == 'adjustment') return 'Adjusted';
  return 'Confirmed';
}

/// Pending and withheld rows are potential awards, not posted changes, so
/// they carry no sign (matching the approved withheld design).
String entryAmount(PointsEntry entry) =>
    entry.isWithheld ? formatPoints(entry.amount) : signedPoints(entry.amount);

String entryDate(BuildContext context, DateTime at) =>
    MaterialLocalizations.of(context).formatMediumDate(at.toLocal());

/// One ledger row. Tapping opens the owner-only entry (M-065).
class PointsEntryTile extends StatelessWidget {
  const PointsEntryTile({super.key, required this.entry, required this.onTap});
  final PointsEntry entry;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final title = entryTitle(entry);
    final status = entryStatusLabel(entry);
    final amount = entryAmount(entry);
    return Semantics(
      container: true,
      label:
          '$title, $status, ${entryDate(context, entry.createdAt)}, $amount Lone Stars',
      child: ExcludeSemantics(
        child: ListTile(
          leading: const CircleAvatar(
              radius: 20,
              backgroundColor: Color(0xFFFFF3CC),
              child: Icon(Icons.star_outline,
                  size: 20, color: KoloVibeColors.navy)),
          title: Text(title),
          subtitle: Text('${entryDate(context, entry.createdAt)} · $status'),
          trailing: Text(amount,
              style: KoloVibeText.heading(16,
                  color: entry.amount < 0
                      ? KoloVibeColors.red
                      : KoloVibeColors.navy)),
          onTap: onTap,
        ),
      ),
    );
  }
}

/// A labelled number: "Pending" / "160".
class PointsStatTile extends StatelessWidget {
  const PointsStatTile(
      {super.key,
      required this.label,
      required this.value,
      required this.onTap});
  final String label;
  final int value;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Card(
        child: ListTile(
          title: Text(label),
          trailing: Text(formatPoints(value),
              style: Theme.of(context).textTheme.titleMedium),
          onTap: onTap,
        ),
      );
}

/// An informational card with one honest explanation.
class PointsNote extends StatelessWidget {
  const PointsNote(this.text, {super.key});
  final String text;

  @override
  Widget build(BuildContext context) => Container(
      width: double.infinity,
      margin: const EdgeInsets.symmetric(vertical: 8),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
          color: const Color(0xFFFFF3CC),
          borderRadius: BorderRadius.circular(KoloVibeRadii.tile)),
      child: Text(text, style: KoloVibeText.body(12, height: 1.45)));
}

/// The non-cash reminder shown wherever points appear.
const nonCashNote =
    'Lone Stars are non-cash recognition points. They are not money, a spendable balance or redeemable value.';

/// The failure state for a points read. A 403 means the account is not an
/// approved creator with a verified email, which is a normal state.
Widget pointsFailureView(BuildContext context, Object error,
    {required VoidCallback onRetry,
    required VoidCallback onSignIn,
    required VoidCallback onStudio}) {
  if (error is ApiFailure && error.kind == FailureKind.forbidden) {
    return LiveStateView.empty(
        title: 'Lone Stars are for approved creators',
        message:
            'They appear here once your creator profile is approved and your email is verified.',
        icon: Icons.lock_outline,
        actionLabel: 'Open Creator Studio',
        onAction: onStudio);
  }
  return LiveStateView.failure(error, onRetry: onRetry, onSignIn: onSignIn);
}
