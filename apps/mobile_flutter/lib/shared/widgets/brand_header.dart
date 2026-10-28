import 'package:flutter/material.dart';
import '../../core/theme/kolovibe_theme.dart';

class BrandHeader extends StatelessWidget {
  const BrandHeader({this.subtitle, super.key});
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 35,
          height: 35,
          decoration: BoxDecoration(
            color: KoloVibeColors.red,
            borderRadius: BorderRadius.circular(11),
          ),
          child: const Icon(Icons.play_arrow_rounded, color: Colors.white),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'KoloVibe',
                style: Theme.of(
                  context,
                ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900),
              ),
              if (subtitle != null)
                Text(subtitle!, style: Theme.of(context).textTheme.labelSmall),
            ],
          ),
        ),
      ],
    );
  }
}
