import 'package:flutter/material.dart';

import '../../app/screen_route.dart';
import '../system/system_ui.dart';
import 'live_account_repository.dart';

class AccountSessionsScreen extends StatefulWidget {
  const AccountSessionsScreen({super.key, required this.repository});

  final LiveAccountRepository repository;

  @override
  State<AccountSessionsScreen> createState() => _AccountSessionsScreenState();
}

class _AccountSessionsScreenState extends State<AccountSessionsScreen> {
  late Future<List<AccountSession>> _sessions;
  bool _revoking = false;
  Object? _failure;

  @override
  void initState() {
    super.initState();
    _sessions = widget.repository.sessions();
  }

  void _reload() => setState(() {
        _failure = null;
        _sessions = widget.repository.sessions();
      });

  Future<void> _revoke(AccountSession session) async {
    final confirmed = await confirmDestructive(
      context,
      title: 'End this session?',
      message: 'The other device will need to sign in again.',
      confirmLabel: 'End session',
    );
    if (!mounted || !confirmed) return;
    setState(() => _revoking = true);
    try {
      await widget.repository.revokeSession(session.id);
      if (mounted) {
        notifySuccess(context, 'Session ended.');
        _reload();
      }
    } catch (failure) {
      if (mounted) setState(() => _failure = failure);
    } finally {
      if (mounted) setState(() => _revoking = false);
    }
  }

  void signIn() {
    const route = ScreenRoute(4);
    Navigator.of(context)
        .pushNamedAndRemoveUntil(route.name, (_) => false, arguments: route);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Active sessions')),
        body: SafeArea(
          child: FutureBuilder<List<AccountSession>>(
            future: _sessions,
            builder: (context, snapshot) {
              if (snapshot.connectionState != ConnectionState.done) {
                return const SystemLoading();
              }
              if (_failure != null || snapshot.hasError) {
                return SystemFailureView(
                  error: _failure ?? snapshot.error!,
                  onRetry: _reload,
                  onSignIn: signIn,
                );
              }
              final sessions = snapshot.data!;
              if (sessions.isEmpty) {
                return const Center(child: Text('No active sessions.'));
              }
              final locale = MaterialLocalizations.of(context);
              return ListView(
                children: [
                  for (final session in sessions)
                    ListTile(
                      title: Text(
                        session.current
                            ? 'Current session'
                            : 'Signed-in session',
                      ),
                      subtitle: Text(
                        'Started ${locale.formatMediumDate(session.createdAt.toLocal())}',
                      ),
                      trailing: session.current
                          ? null
                          : TextButton(
                              onPressed:
                                  _revoking ? null : () => _revoke(session),
                              child: const Text('End session'),
                            ),
                    ),
                ],
              );
            },
          ),
        ),
      );
}
