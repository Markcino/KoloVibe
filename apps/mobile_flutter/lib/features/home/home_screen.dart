import 'package:flutter/material.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/brand_header.dart';
import '../../shared/widgets/section_header.dart';
import '../../shared/widgets/empty_section.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return CustomScrollView(
      key: const PageStorageKey('home'),
      slivers: [
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 30),
          sliver: SliverList(
            delegate: SliverChildListDelegate([
              const BrandHeader(subtitle: 'OUR STORIES. OUR RHYTHM. OUR VIBE.'),
              const SizedBox(height: 32),
              Text('Discover what moves us.', style: theme.textTheme.headlineMedium),
              const SizedBox(height: 8),
              Text('Original voices from Liberia and beyond.', style: theme.textTheme.bodyMedium),
              const SizedBox(height: 26),
              Container(
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: KoloVibeColors.deepNavy,
                  borderRadius: BorderRadius.circular(23),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('MADE HERE. FELT EVERYWHERE.', style: theme.textTheme.labelSmall?.copyWith(color: KoloVibeColors.gold, letterSpacing: 1)),
                    const SizedBox(height: 16),
                    const Text('Every story starts somewhere.', style: TextStyle(color: Colors.white, fontSize: 27, fontWeight: FontWeight.w800, height: 1.1)),
                    const SizedBox(height: 12),
                    const Text('Explore original films, fresh sounds and the creators shaping our culture.', style: TextStyle(color: Color(0xFFD7E3F5), height: 1.4)),
                    const SizedBox(height: 24),
                    const Wrap(spacing: 8, runSpacing: 8, children: [
                      Chip(label: Text('Original videos')),
                      Chip(label: Text('Creators')),
                      Chip(label: Text('Culture')),
                    ]),
                  ],
                ),
              ),
              const SizedBox(height: 28),
              const SectionHeader(title: 'Around KoloVibe', subtitle: 'One place to discover more of what matters.'),
              const Row(
                children: [
                  Expanded(child: _Destination(icon: Icons.smart_display_outlined, title: 'Videos')),
                  SizedBox(width: 10),
                  Expanded(child: _Destination(icon: Icons.explore_outlined, title: 'Explore')),
                  SizedBox(width: 10),
                  Expanded(child: _Destination(icon: Icons.person_outline, title: 'Creators')),
                ],
              ),
              const SizedBox(height: 28),
              const SectionHeader(title: 'Featured originals'),
              const EmptySection(
                icon: Icons.movie_filter_outlined,
                title: 'The next great story is coming.',
                message: 'Original videos will appear here as soon as they are published.',
              ),
            ]),
          ),
        ),
      ],
    );
  }
}

class _Destination extends StatelessWidget {
  const _Destination({required this.icon, required this.title});
  final IconData icon;
  final String title;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 18, horizontal: 8),
        child: Column(
          children: [
            Icon(icon, color: KoloVibeColors.red, size: 27),
            const SizedBox(height: 8),
            Text(title, style: Theme.of(context).textTheme.labelLarge),
          ],
        ),
      ),
    );
  }
}
