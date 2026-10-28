import 'package:flutter/material.dart';
import '../../shared/widgets/empty_section.dart';

class CreateScreen extends StatelessWidget {
  const CreateScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 22, 20, 30),
      children: [
        Text('Create an original', style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: 8),
        const Text('Your stories deserve to be seen.'),
        const SizedBox(height: 32),
        const EmptySection(
          icon: Icons.video_call_outlined,
          title: 'Make something worth sharing.',
          message: 'Video publishing requires a creator account. Sign-in and upload services will be enabled when the secure backend is connected.',
        ),
      ],
    );
  }
}
