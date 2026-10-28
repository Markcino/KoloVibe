import 'package:flutter/material.dart';
import '../../shared/widgets/empty_section.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 22, 20, 30),
      children: [
        Text('Your KoloVibe', style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: 8),
        const Text('Your account, your originals and your creative home.'),
        const SizedBox(height: 30),
        const EmptySection(
          icon: Icons.account_circle_outlined,
          title: 'Make it yours.',
          message: 'Account access will be available after secure identity integration.',
        ),
      ],
    );
  }
}
