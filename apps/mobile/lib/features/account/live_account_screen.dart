import 'package:flutter/material.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/kolo_components.dart';

import '../../app/screen_route.dart';
import '../../core/presentation/design_node.dart';
import '../system/system_ui.dart';
import '../../core/network/api_client.dart';
import '../shell/main_shell.dart';
import 'live_account_repository.dart';

class LiveAccountScreen extends StatefulWidget {
  const LiveAccountScreen({
    super.key,
    required this.repository,
    required this.catalog,
  });
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
        body: SafeArea(
          child: FutureBuilder<LiveAccount?>(
            future: account,
            builder: (context, snapshot) {
              if (!snapshot.hasData &&
                  !snapshot.hasError &&
                  snapshot.connectionState != ConnectionState.done) {
                return const SystemLoading();
              }
              if (snapshot.hasError) {
                return SystemFailureView(
                  error: snapshot.error!,
                  onRetry: () => setState(() {
                    account = widget.repository.currentAccount();
                  }),
                  onSignIn: () => navigate(4),
                );
              }
              final user = snapshot.data;
              if (user == null) {
                return SystemFailureView(
                  error: const ApiFailure(401, 'Sign in again.'),
                  onSignIn: () => navigate(4),
                );
              }
              final creator = user.roles.contains('creator');
              return SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Row(children: [
                        KoloAvatar(name: user.displayName, size: 64),
                        const SizedBox(width: 12),
                        Expanded(
                            child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                              Text(user.displayName,
                                  style: KoloVibeText.heading(20)),
                              const SizedBox(height: 2),
                              Text(user.email, style: KoloVibeText.body(12)),
                              Text('Roles: ${user.roles.join(', ')}',
                                  style: KoloVibeText.body(12)),
                            ])),
                      ]),
                      if (creator) ...[
                        const SizedBox(height: 12),
                        const Wrap(spacing: 8, runSpacing: 8, children: [
                          KoloBadge('Creator enabled', filled: true),
                        ]),
                        const SizedBox(height: 16),
                        Container(
                          padding: const EdgeInsets.all(20),
                          decoration: BoxDecoration(
                              color: KoloVibeColors.navy,
                              borderRadius:
                                  BorderRadius.circular(KoloVibeRadii.card)),
                          child: Column(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                Text('YOUR CREATIVE HOME',
                                    style: KoloVibeText.body(10,
                                        weight: FontWeight.w700,
                                        color: KoloVibeColors.gold,
                                        letterSpacing: 0.6)),
                                const SizedBox(height: 8),
                                Text('Create. Publish. Be heard.',
                                    style: KoloVibeText.heading(22,
                                        color: Colors.white, height: 1.2)),
                                const SizedBox(height: 16),
                                FilledButton(
                                    onPressed: () => navigate(37),
                                    child: const Text('Open Creator Studio')),
                              ]),
                        ),
                      ],
                      const SizedBox(height: 8),
                      KoloListRow(
                          title: 'Edit personal profile',
                          subtitle: 'Your name and account photo',
                          icon: Icons.person_outline,
                          onTap: () => navigate(80)),
                      KoloListRow(
                          title: 'Account settings',
                          icon: Icons.settings_outlined,
                          onTap: () => navigate(81)),
                      KoloListRow(
                          title: 'Account status',
                          icon: Icons.verified_user_outlined,
                          onTap: () => navigate(77)),
                      KoloListRow(
                          title: 'Help & Support',
                          icon: Icons.help_outline,
                          onTap: () => navigate(89)),
                      if (creator) ...[
                        KoloListRow(
                            title: 'Create a video',
                            icon: Icons.videocam_outlined,
                            onTap: () => navigate(37)),
                        KoloListRow(
                            title: 'Creator studio',
                            subtitle: 'Public bio and identity',
                            icon: Icons.movie_creation_outlined,
                            onTap: () => navigate(38)),
                      ] else
                        KoloListRow(
                            title: 'Become a creator',
                            icon: Icons.movie_creation_outlined,
                            onTap: () => navigate(14)),
                      KoloListRow(
                          title: 'Active sessions',
                          icon: Icons.devices_outlined,
                          onTap: () {
                            const route = ScreenRoute(83);
                            Navigator.of(context)
                                .pushNamed(route.name, arguments: route);
                          }),
                      if (creator)
                        KoloListRow(
                            title: 'Lone Stars',
                            subtitle: 'Non-cash community recognition',
                            icon: Icons.star_outline,
                            onTap: () {
                              const route = ScreenRoute(61);
                              Navigator.of(context)
                                  .pushNamed(route.name, arguments: route);
                            }),
                      const SizedBox(height: 24),
                      FilledButton(
                        onPressed: () => navigate(90),
                        child: const Text('Sign out'),
                      ),
                    ]),
              );
            },
          ),
        ),
        bottomNavigationBar: MainShell(
          navigation: widget.catalog[79].named('Primary navigation')!,
          screen: 79,
          onSelected: navigate,
        ),
      );
}
