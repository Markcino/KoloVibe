import 'package:flutter/material.dart';

class BrandHeader extends StatelessWidget {
  const BrandHeader({this.subtitle, this.darkBackground = false, super.key});
  final String? subtitle;
  final bool darkBackground;

  @override
  Widget build(BuildContext context) {
    if (!darkBackground) {
      return Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Image.asset('assets/images/landscape_logo_with_name.png',
              width: 145, height: 45, semanticLabel: 'KoloVibe'),
          if (subtitle != null)
            Text(subtitle!, style: Theme.of(context).textTheme.labelSmall),
        ],
      );
    }
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Image.asset('assets/images/logo.png',
            width: 35, height: 35, semanticLabel: 'KoloVibe logo'),
        const SizedBox(width: 10),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'KoloVibe',
              style: Theme.of(
                context,
              ).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w900,
                    color: darkBackground ? Colors.white : null,
                  ),
            ),
            if (subtitle != null)
              Text(subtitle!, style: Theme.of(context).textTheme.labelSmall),
          ],
        ),
      ],
    );
  }
}
