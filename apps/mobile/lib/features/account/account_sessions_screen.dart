import 'package:flutter/material.dart';

import '../../core/network/api_client.dart';
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

  @override
  void initState() {
    super.initState();
    _sessions = widget.repository.sessions();
  }

  void _reload() => setState(() => _sessions = widget.repository.sessions());

  Future<void> _revoke(AccountSession session) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('End this session?'),
        content: const Text('The other device will need to sign in again.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('End session'),
          ),
        ],
      ),
    );
    if (!mounted || confirmed != true) return;
    setState(() => _revoking = true);
    try {
      await widget.repository.revokeSession(session.id);
    } on ApiFailure catch (failure) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(failure.message)),
        );
      }
    } finally {
      if (mounted) {
        _revoking = false;
        _reload();
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Active sessions')),
        body: SafeArea(
          child: FutureBuilder<List<AccountSession>>(
            future: _sessions,
            builder: (context, snapshot) {
              if (snapshot.connectionState != ConnectionState.done) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snapshot.hasError) {
                final error = snapshot.error;
                return Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(error is ApiFailure
                          ? error.message
                          : 'Could not load sessions.'),
                      TextButton(
                          onPressed: _reload, child: const Text('Try again')),
                    ],
                  ),
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
                      title: Text(session.current
                          ? 'Current session'
                          : 'Signed-in session'),
                      subtitle: Text(
                          'Started ${locale.formatMediumDate(session.createdAt.toLocal())}'),
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
