import 'package:flutter/material.dart';
import '../../app/screen_route.dart';
import '../../core/presentation/design_node.dart';
import '../../core/presentation/feature_repository.dart';
import '../shell/main_shell.dart';
import 'live_account_repository.dart';

class LiveAccountScreen extends StatefulWidget {
  const LiveAccountScreen({super.key, required this.repository, required this.catalog});
  final LiveAccountRepository repository;
  final DesignCatalog catalog;

  @override
  State<LiveAccountScreen> createState() => _LiveAccountScreenState();
}

class _LiveAccountScreenState extends State<LiveAccountScreen> {
  late Future<LiveAccount?> account;

  @override
  void initState() {
    super.initState();
    account = widget.repository.currentAccount();
  }

  void navigate(int target) {
    final route = ScreenRoute(target);
    Navigator.of(context).pushReplacementNamed(route.name, arguments: route);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('My account')),
    body: SafeArea(child: FutureBuilder<LiveAccount?>(
      future: account,
      builder: (context, snapshot) {
        if (!snapshot.hasData && !snapshot.hasError && snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return const Center(child: Text('Account service is temporarily unavailable.'));
        }
        final user = snapshot.data;
        if (user == null) {
          return Center(child: FilledButton(onPressed: () => navigate(4), child: const Text('Sign in')));
        }
        return ListView(padding: const EdgeInsets.all(24), children: [
          Text(user.displayName, style: Theme.of(context).textTheme.headlineMedium),
          const SizedBox(height: 8), Text(user.email),
          const SizedBox(height: 24),
          ListTile(
            title: const Text('Active sessions'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () {
              const route = ScreenRoute(83);
              Navigator.of(context).pushNamed(route.name, arguments: route);
            },
          ),
          FilledButton(onPressed: () async {
            await widget.repository.execute(const UiRequest(UiOperation.signOut));
            if (mounted) navigate(2);
          }, child: const Text('Sign out')),
        ]);
      },
    )),
    bottomNavigationBar: MainShell(
      navigation: widget.catalog[79].named('Primary navigation')!,
      screen: 79, onSelected: navigate,
    ),
  );
}
