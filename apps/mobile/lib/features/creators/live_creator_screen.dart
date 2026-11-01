import 'package:flutter/material.dart';
import '../../core/network/api_client.dart';
import 'live_creator_repository.dart';

class LiveCreatorScreen extends StatefulWidget {
  const LiveCreatorScreen(
      {super.key, required this.id, required this.repository});
  final String id;
  final LiveCreatorRepository repository;

  @override
  State<LiveCreatorScreen> createState() => _LiveCreatorScreenState();
}

class _LiveCreatorScreenState extends State<LiveCreatorScreen> {
  LiveCreator? profile;
  Object? error;
  bool loading = true;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final value = await widget.repository.detail(widget.id);
      if (mounted) setState(() => profile = value);
    } on ApiFailure catch (failure) {
      if (mounted) setState(() => error = failure);
    } on FormatException catch (failure) {
      if (mounted) setState(() => error = failure);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Creator')),
        body: SafeArea(child: Builder(
          builder: (context) {
            if (loading) {
              return const Center(child: CircularProgressIndicator());
            }
            if (error != null) {
              final failure = error;
              final missing = failure is ApiFailure && failure.status == 404;
              return Center(
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                Semantics(
                    liveRegion: true,
                    child: Text(missing
                        ? 'This creator is not available for public viewing.'
                        : 'Creators are temporarily unavailable.')),
                if (!missing)
                  OutlinedButton(
                    onPressed: load,
                    child: const Text('Try again'),
                  ),
              ]));
            }
            final creator = profile!;
            return ListView(padding: const EdgeInsets.all(24), children: [
              Text('@${creator.handle}',
                  style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 16),
              Text(creator.bio),
            ]);
          },
        )),
      );
}
