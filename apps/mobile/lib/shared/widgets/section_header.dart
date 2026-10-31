import 'package:flutter/material.dart';

class SectionHeader extends StatelessWidget {
  const SectionHeader({required this.title, this.subtitle, super.key});
  final String title;
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: theme.textTheme.titleLarge),
          if (subtitle != null)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(subtitle!, style: theme.textTheme.bodyMedium),
            ),
        ],
      ),
    );
  }
}
