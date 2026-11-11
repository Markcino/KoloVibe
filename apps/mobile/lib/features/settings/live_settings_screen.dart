import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import '../../core/presentation/design_node.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../account/live_account_repository.dart';
import '../shell/main_shell.dart';
import 'live_settings_repository.dart';

class LiveSettingsScreen extends StatefulWidget {
  const LiveSettingsScreen(
      {super.key,
      required this.route,
      required this.catalog,
      required this.repository,
      required this.account});
  final ScreenRoute route;
  final DesignCatalog catalog;
  final LiveSettingsRepository repository;
  final LiveAccountRepository account;

  @override
  State<LiveSettingsScreen> createState() => _LiveSettingsScreenState();
}

class _LiveSettingsScreenState extends State<LiveSettingsScreen> {
  final password = TextEditingController();
  final acknowledgement = TextEditingController();
  bool agreed = false, busy = false;
  Object? error;
  NotificationChoices? choices;
  LiveAccount? account;
  List<PrivacyReceipt>? receipts;

  int get id => widget.route.screen;

  @override
  void initState() {
    super.initState();
    load();
  }

  @override
  void dispose() {
    password.clear();
    acknowledgement.clear();
    password.dispose();
    acknowledgement.dispose();
    super.dispose();
  }

  Future<void> load() async {
    setState(() => error = null);
    try {
      if ({85, 92}.contains(id)) {
        final value = await widget.account.currentAccount();
        if (value == null) throw const ApiFailure(401, 'Sign in again.');
        if (mounted) setState(() => account = value);
      }
      if (id == 86) {
        final value = await widget.repository.preferences();
        if (mounted) setState(() => choices = value);
      }
      if ({93, 94}.contains(id)) {
        final value = await widget.repository.privacyRequests();
        if (mounted) setState(() => receipts = value);
      }
    } catch (failure) {
      if (mounted) setState(() => error = failure);
    }
  }

  void go(int target, {bool replace = false}) {
    final route = ScreenRoute(target);
    if (replace) {
      Navigator.of(context).pushReplacementNamed(route.name, arguments: route);
    } else {
      Navigator.of(context).pushNamed(route.name, arguments: route);
    }
  }

  Future<void> saveChoices(NotificationChoices value) async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final saved = await widget.repository.updatePreferences(value);
      if (mounted) setState(() => choices = saved);
    } catch (failure) {
      if (mounted) setState(() => error = failure);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> submitDeletion() async {
    if (busy ||
        acknowledgement.text.trim() != 'DELETE' ||
        !agreed ||
        password.text.isEmpty) {
      setState(() => error = const FormatException(
          'Enter DELETE, confirm, and provide your password.'));
      return;
    }
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.repository.requestPrivacy('deletion', password.text);
      password.clear();
      if (mounted) go(93, replace: true);
    } catch (failure) {
      if (mounted) setState(() => error = failure);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> submitAccess() async {
    var input = '';
    final current = await showDialog<String>(
        context: context,
        builder: (dialogContext) => AlertDialog(
              title: const Text('Request your account data'),
              content: TextField(
                  onChanged: (value) => input = value,
                  obscureText: true,
                  decoration:
                      const InputDecoration(labelText: 'Current password')),
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(dialogContext),
                    child: const Text('Cancel')),
                FilledButton(
                    onPressed: () => Navigator.pop(dialogContext, input),
                    child: const Text('Send request')),
              ],
            ));
    input = '';
    if (current == null || current.isEmpty || !mounted) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.repository.requestPrivacy('access', current);
      if (mounted) go(94);
    } catch (failure) {
      if (mounted) setState(() => error = failure);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  String get title => switch (id) {
        84 => 'Privacy settings',
        85 => 'Security settings',
        86 => 'Notification preferences',
        91 => 'Delete account request',
        92 => 'Confirm account deletion',
        93 => 'Deletion request received',
        94 => 'Privacy request received',
        _ => 'Settings',
      };

  @override
  Widget build(BuildContext context) {
    final navigation = widget.catalog[id].named('Primary navigation');
    return Scaffold(
      appBar: AppBar(
          title: Text(title),
          backgroundColor: KoloVibeColors.lavender,
          leading: IconButton(
              icon: SvgPicture.asset('assets/images/add18c048fedbc53b74e.svg',
                  width: 24, height: 24),
              tooltip: 'Back',
              onPressed: () => Navigator.maybePop(context))),
      body: SafeArea(
          child: ListView(
              padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
              children: [
            if (error != null)
              Padding(
                  padding: const EdgeInsets.only(bottom: 16),
                  child: Semantics(
                      liveRegion: true,
                      child: Text(
                          error is ApiFailure
                              ? (error as ApiFailure).message
                              : error is FormatException
                                  ? (error as FormatException).message
                                  : 'This service is unavailable. Please try again.',
                          style: const TextStyle(color: KoloVibeColors.red)))),
            switch (id) {
              84 => privacy(),
              85 => security(),
              86 => notifications(),
              91 => deletionIntro(),
              92 => deletionConfirm(),
              93 || 94 => receipt(),
              _ => const SizedBox.shrink(),
            },
          ])),
      bottomNavigationBar: navigation == null
          ? null
          : MainShell(navigation: navigation, screen: id, onSelected: go),
    );
  }

  Widget heading(String value) => Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Text(value,
          style: Theme.of(context)
              .textTheme
              .headlineMedium
              ?.copyWith(color: KoloVibeColors.navy, fontSize: 28)));

  Widget note(String value) => Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Text(value,
          style: const TextStyle(color: KoloVibeColors.muted, height: 1.5)));

  Widget panel(List<Widget> children) => Card(
      child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: children)));

  Widget privacy() =>
      Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        heading('Your data. A clearer view.'),
        note(
            'Understand the information associated with your account and the choices available under the current policy.'),
        panel([
          ListTile(
              title: const Text('Account information'), onTap: () => go(85)),
          ListTile(title: const Text('Privacy policy'), onTap: () => go(88)),
          ListTile(
              title: const Text('Delete account request'), onTap: () => go(91)),
        ]),
        const SizedBox(height: 16),
        OutlinedButton(
            onPressed: busy ? null : submitAccess,
            child: const Text('Request account data')),
        note(
            'Requests are recorded for handling under the current policy. No data is deleted or exported immediately.'),
      ]);

  Widget security() =>
      Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        heading('A safer space for your voice.'),
        panel([
          const Text('Email verified',
              style: TextStyle(color: KoloVibeColors.green)),
          const SizedBox(height: 6),
          account == null
              ? const CircularProgressIndicator()
              : Text(account!.email),
          ListTile(title: const Text('Change password'), onTap: () => go(82)),
          ListTile(title: const Text('Active sessions'), onTap: () => go(83)),
        ]),
        note('Never share a password or verification code.'),
      ]);

  Widget notifications() {
    final value = choices;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      heading('Stay in the loop. On your terms.'),
      if (value == null && error == null)
        const Center(child: CircularProgressIndicator()),
      if (value != null)
        panel([
          SwitchListTile(
              title: const Text('Account notices'),
              subtitle:
                  const Text('Essential account information, where supported.'),
              value: value.email,
              onChanged: busy
                  ? null
                  : (enabled) =>
                      saveChoices(NotificationChoices(enabled, value.push))),
          SwitchListTile(
              title: const Text('Creator status updates'),
              subtitle: const Text(
                  'Delivery depends on account and service availability.'),
              value: value.push,
              onChanged: busy
                  ? null
                  : (enabled) =>
                      saveChoices(NotificationChoices(value.email, enabled))),
        ]),
      const SizedBox(height: 16),
      panel([
        const Text('Device notifications are off',
            style: TextStyle(
                fontWeight: FontWeight.w600, color: KoloVibeColors.navy)),
        const Text(
            'Check device settings if you want to allow app notifications. Enabling permission does not guarantee delivery.')
      ]),
      note(
          'These choices are saved to your account. Notification delivery is not yet enabled.'),
    ]);
  }

  Widget deletionIntro() =>
      Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        SvgPicture.asset('assets/images/e2e09b68a17805674b06.svg',
            width: 40, height: 40, alignment: Alignment.centerLeft),
        const SizedBox(height: 16),
        heading('Before you leave.'),
        note(
            'Account deletion affects access, your public profile, and associated content under the applicable account and privacy policies.'),
        panel([
          const Text('Profile & access',
              style: TextStyle(fontWeight: FontWeight.w600)),
          const Text('You may lose access to your account and creator tools.'),
          const SizedBox(height: 16),
          const Text('Published content',
              style: TextStyle(fontWeight: FontWeight.w600)),
          const Text('Content handling follows the current deletion policy.')
        ]),
        const SizedBox(height: 16),
        note(
            'This is a sensitive account action. Your password is required to record the request. This step does not delete your account.'),
        FilledButton(
            onPressed: () => go(92),
            child: const Text('Verify identity to continue')),
        OutlinedButton(
            onPressed: () => go(79), child: const Text('Keep my account')),
      ]);

  Widget deletionConfirm() =>
      Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        heading('This is your final confirmation.'),
        panel([
          SvgPicture.asset('assets/images/d2e1a85a4719e38d2349.svg',
              width: 20, height: 20),
          const Text('Identity verification required',
              style: TextStyle(color: KoloVibeColors.green)),
          Text(account == null
              ? 'Checking your account…'
              : 'You are requesting deletion for ${account!.email}.')
        ]),
        note(
            'This records a deletion request under the current policy. It does not sign you out or delete data now.'),
        TextField(
            controller: acknowledgement,
            decoration:
                const InputDecoration(labelText: 'Type DELETE to acknowledge'),
            autocorrect: false),
        const SizedBox(height: 12),
        TextField(
            controller: password,
            obscureText: true,
            decoration: const InputDecoration(labelText: 'Current password')),
        CheckboxListTile(
            value: agreed,
            onChanged: (value) => setState(() => agreed = value ?? false),
            title: const Text(
                'I understand the account and content consequences described in the deletion policy.')),
        FilledButton(
            style: FilledButton.styleFrom(backgroundColor: KoloVibeColors.red),
            onPressed: busy || account == null ? null : submitDeletion,
            child: const Text('Confirm deletion request')),
        OutlinedButton(
            onPressed: () => go(79),
            child: const Text('Cancel — keep my account')),
        note(
            'Handling and any remaining obligations follow the applicable policy. No recovery period is promised.'),
      ]);

  Widget receipt() {
    final kind = id == 93 ? 'deletion' : 'access';
    final match = receipts?.where((item) => item.kind == kind).toList();
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      heading(id == 93
          ? 'Your request is recorded.'
          : 'We’ve recorded your privacy request.'),
      if (receipts == null && error == null)
        const Center(child: CircularProgressIndicator()),
      if (match != null && match.isEmpty)
        note('No received request was found for this account.'),
      if (match != null && match.isNotEmpty)
        panel([
          const Text('Request status',
              style: TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          Text(
              'Received · Awaiting handling · ${match.first.createdAt.toLocal().toString().split(' ').first}'),
        ]),
      note(
          'This acknowledgment does not mean associated information has been deleted or exported.'),
      OutlinedButton(
          onPressed: () => go(88),
          child: const Text('Read privacy information')),
      TextButton(
          onPressed: () => go(84),
          child: const Text('Return to privacy settings')),
    ]);
  }
}
