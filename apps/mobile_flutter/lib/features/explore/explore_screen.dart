import 'package:flutter/material.dart';
import '../../shared/widgets/section_header.dart';
import '../../shared/widgets/empty_section.dart';

class ExploreScreen extends StatefulWidget {
  const ExploreScreen({super.key});

  @override
  State<ExploreScreen> createState() => _ExploreScreenState();
}

class _ExploreScreenState extends State<ExploreScreen> {
  String category = 'All';
  static const categories = ['All', 'Hipco', 'Afrobeats', 'Comedy', 'Short films', 'Culture', 'Documentaries'];

  @override
  Widget build(BuildContext context) {
    return ListView(
      key: const PageStorageKey('explore'),
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 30),
      children: [
        Text('Explore', style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: 12),
        const TextField(
          textInputAction: TextInputAction.search,
          decoration: InputDecoration(
            hintText: 'Search videos and creators',
            prefixIcon: Icon(Icons.search),
          ),
        ),
        const SizedBox(height: 20),
        SizedBox(
          height: 43,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: categories.length,
            separatorBuilder: (_, _) => const SizedBox(width: 8),
            itemBuilder: (context, index) => ChoiceChip(
              label: Text(categories[index]),
              selected: category == categories[index],
              onSelected: (_) => setState(() => category = categories[index]),
            ),
          ),
        ),
        const SizedBox(height: 28),
        SectionHeader(title: category == 'All' ? 'Discover originals' : category),
        const EmptySection(
          icon: Icons.travel_explore,
          title: 'Fresh voices belong here.',
          message: 'Browse original stories when published content becomes available.',
        ),
      ],
    );
  }
}
