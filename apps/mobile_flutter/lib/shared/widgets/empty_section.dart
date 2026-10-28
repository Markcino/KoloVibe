import 'package:flutter/material.dart';
import '../../core/theme/kolovibe_theme.dart';

class EmptySection extends StatelessWidget {
  const EmptySection({
    required this.icon,
    required this.title,
    required this.message,
    this.action,
    super.key,
  });

  final IconData icon;
  final String title;
  final String message;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 26, horizontal: 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircleAvatar(
              radius: 29,
              backgroundColor: KoloVibeColors.softBlue,
              child: Icon(icon, color: KoloVibeColors.navy, size: 28),
            ),
            const SizedBox(height: 14),
            Text(title, style: theme.textTheme.titleMedium, textAlign: TextAlign.center),
            const SizedBox(height: 8),
            Text(message, style: theme.textTheme.bodyMedium, textAlign: TextAlign.center),
            if (action != null) ...[const SizedBox(height: 18), action!],
          ],
        ),
      ),
    );
  }
}
