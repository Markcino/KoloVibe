import 'package:flutter/material.dart';
import 'live_creator_repository.dart';

class LiveCreatorScreen extends StatelessWidget {
  const LiveCreatorScreen({super.key, required this.id, required this.repository});
  final String id;
  final LiveCreatorRepository repository;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Creator')),
    body: SafeArea(child: FutureBuilder<LiveCreator>(
      future: repository.detail(id),
      builder: (context, snapshot) {
        if (!snapshot.hasData && !snapshot.hasError) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return const Center(child: Text('This creator is unavailable.'));
        }
        final creator = snapshot.data!;
        return ListView(padding: const EdgeInsets.all(24), children: [
          Text('@${creator.handle}', style: Theme.of(context).textTheme.headlineMedium),
          const SizedBox(height: 16), Text(creator.bio),
        ]);
      },
    )),
  );
}
