import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../shared/widgets/kolo_components.dart';
import 'live_settings_repository.dart';

/// Mandate 3.3: the person's own access export, shown in the app. It is held in memory only and is gone when the
/// person leaves this view; nothing is written to the device unless they copy it themselves.
class AccessExportView extends StatelessWidget {
  const AccessExportView({super.key, required this.export});
  final AccessExport export;

  static const serviceLabels = {
    'identity': 'Account',
    'engagement': 'Likes, follows and watching',
    'creators': 'Creator profile',
    'moderation': 'Reports, appeals and decisions',
    'content': 'Videos',
    'business': 'Businesses',
  };

  static String label(String name) {
    final words = name.replaceAll('_', ' ');
    return words[0].toUpperCase() + words.substring(1);
  }

  static String value(Object? value) => switch (value) {
        null => '—',
        final List<dynamic> items => items.join(', '),
        _ => '$value',
      };

  Widget _row(BuildContext context, Map<String, Object?> row) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (final entry in row.entries)
              SelectableText('${label(entry.key)}: ${value(entry.value)}'),
          ],
        ),
      );

  Future<void> _copy(BuildContext context) async {
    await Clipboard.setData(ClipboardData(text: export.toText()));
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
          content: Text('Your data was copied. Paste it somewhere safe.')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context).textTheme;
    final services = [
      for (final name in serviceLabels.keys)
        if (export.services[name] case final part?) MapEntry(name, part),
    ];
    return Scaffold(
      appBar: AppBar(title: const Text('Your data')),
      body: SafeArea(
        child: ListView(
          key: const ValueKey('access-export'),
          padding: const EdgeInsets.all(24),
          children: [
            const KoloHeadline('Your data', size: 26),
            const SizedBox(height: 12),
            Text(
              'Available until ${export.expiresAt.toUtc().toIso8601String()}. '
              'It is shown here only and is not saved on this device.',
              style: theme.bodyMedium,
            ),
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: () => _copy(context),
              child: const Text('Copy all as text'),
            ),
            const SizedBox(height: 8),
            Text(
              'Copied text can be read by other apps on this device until you copy something else.',
              style: theme.bodySmall,
            ),
            for (final MapEntry(key: service, value: part) in services)
              ExpansionTile(
                key: ValueKey('export-$service'),
                title: Text(serviceLabels[service]!),
                childrenPadding: const EdgeInsets.symmetric(horizontal: 16),
                expandedCrossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (final MapEntry(key: name, value: rows)
                      in part.data.entries) ...[
                    Padding(
                      padding: const EdgeInsets.only(top: 8, bottom: 8),
                      child: Text('${label(name)} (${rows.length})',
                          style: theme.titleSmall),
                    ),
                    if (rows.isEmpty) const Text('None'),
                    for (final row in rows) _row(context, row),
                    if (part.truncated.contains(name))
                      const Text('Only the first 5,000 entries are included.'),
                  ],
                  if (part.withheld.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 8, bottom: 16),
                      child: Text(
                        'Not included yet, pending a policy decision: '
                        '${part.withheld.map(label).join(', ')}.',
                        style: theme.bodySmall,
                      ),
                    ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}
