import 'package:flutter/material.dart';

import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import '../../core/platform/device_bridge.dart';
import '../../core/presentation/design_node.dart';
import '../account/live_account_repository.dart';
import '../system/system_ui.dart';

/// Static recipe policy/help content, live account settings and real sign-out.
class LiveInformationScreen extends StatefulWidget {
  const LiveInformationScreen({
    super.key,
    required this.screen,
    required this.catalog,
    required this.account,
    required this.device,
    this.links,
  });
  final int screen;
  final DesignCatalog catalog;
  final LiveAccountRepository account;
  final DeviceBridge device;
  final PublicLinks? links;
  @override
  State<LiveInformationScreen> createState() => _LiveInformationScreenState();
}

class _LiveInformationScreenState extends State<LiveInformationScreen> {
  LiveAccount? user;
  Object? error;
  bool loading = false, busy = false, signedOut = false, terms = false;
  int get id => widget.screen;
  @override
  void initState() {
    super.initState();
    if ({81, 90}.contains(id)) load();
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final value = await widget.account.currentAccount();
      if (value == null) throw const ApiFailure(401, 'Sign in again.');
      if (mounted) setState(() => user = value);
    } catch (failure) {
      if (mounted) setState(() => error = failure);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  void go(int target, {bool reset = false}) {
    final route = ScreenRoute(target);
    if (reset) {
      Navigator.of(context)
          .pushNamedAndRemoveUntil(route.name, (_) => false, arguments: route);
    } else {
      Navigator.of(context).pushNamed(route.name, arguments: route);
    }
  }

  Future<void> logout() async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.account.signOut();
      if (mounted) go(2, reset: true);
    } catch (failure) {
      if (mounted) {
        setState(() {
          error = failure;
          signedOut = failure is ApiFailure;
        });
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Widget heading(String value) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 12),
        child: Text(value, style: Theme.of(context).textTheme.headlineSmall),
      );
  Widget row(String title, int target, [String? subtitle]) => ListTile(
        title: Text(title),
        subtitle: subtitle == null ? null : Text(subtitle),
        trailing: const Icon(Icons.chevron_right),
        onTap: busy ? null : () => go(target),
      );
  Widget? webLink(String title, String path) {
    final url = (widget.links ?? PublicLinks()).page(path);
    if (url == null) return null;
    return TextButton(
      onPressed: () async {
        final opened = await widget.device.openUrl(url);
        if (!mounted || opened) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('This page could not be opened on your device.'),
          ),
        );
      },
      child: Text(title),
    );
  }

  List<Widget> content() => switch (id) {
        14 => [
            heading('Create something only you can.'),
            heading('Original starts with you.'),
            const Text(
              'Share work you own, respect your community and build an authentic audience.',
            ),
            heading('Creator access is role-based'),
            const Text(
              'Complete creator setup. Publishing becomes available when your account is enabled.',
            ),
            row('Start creator setup', 36),
            row('Keep exploring', 19),
          ],
        81 => [
            heading('Your account'),
            if (user != null) Text(user!.email),
            row('Security', 85, 'Email, password and sign-in access'),
            row('Privacy', 84, 'Your data and policy information'),
            row('Notifications', 86, 'Device permissions and preferences'),
            heading('Community & support'),
            row('Community guidelines', 87),
            row('Terms & Privacy', 88),
            row('Help & Support', 89),
            row('Sign out', 90),
            row('Delete account', 91),
          ],
        87 => [
            heading('A good vibe starts with respect.'),
            const Text(
              'These principles help keep original voices welcome. Refer to the current in-app guidelines for the full policy.',
            ),
            heading('Respect people'),
            const Text('No harassment, hateful targeting or threats.'),
            heading('Share responsibly'),
            const Text(
                'Avoid harmful content and protect personal information.'),
            heading('Honour original work'),
            const Text('Share only content you own or have permission to use.'),
            heading('Keep engagement genuine'),
            const Text('Don’t manipulate activity or recognition.'),
            const Text(
              'Content decisions and review options follow the applicable moderation policy.',
            ),
            if (webLink('Read current community guidelines',
                    '/community-guidelines')
                case final link?)
              link,
          ],
        88 => [
            Wrap(
              children: [
                ChoiceChip(
                  label: const Text('Privacy information'),
                  selected: !terms,
                  onSelected: (_) => setState(() => terms = false),
                ),
                ChoiceChip(
                  label: const Text('Terms'),
                  selected: terms,
                  onSelected: (_) => setState(() => terms = true),
                ),
              ],
            ),
            heading('Understand your relationship with KoloVibe.'),
            const Text(
              'A guide to key topics. The current published Terms and Privacy Policy govern the service.',
            ),
            heading('In this policy'),
            const Text(
              'Your account information\nHow information is used\nYour available privacy choices\nContent rights and responsibilities',
            ),
            const Text(
              'Read the complete, current documents. Available requests and actions depend on applicable policy.',
            ),
            if (webLink(
              terms ? 'Read current Terms' : 'Read current Privacy Policy',
              terms ? '/terms' : '/privacy',
            )
                case final link?)
              link,
          ],
        89 => [
            heading('Let’s find your way forward.'),
            heading('Popular help topics'),
            row('I can’t sign in', 9, 'Password reset and verification'),
            row('Video won’t play', 34, 'Connection and Data Saver guidance'),
            row('Upload or review status', 40,
                'Understand your video’s next step'),
            row('Lone Stars explained', 68, 'Non-cash community recognition'),
            if (webLink('View available support options', '/help')
                case final link?)
              link,
            const Text(
              'Support channels and availability are shown by the service. No response time is guaranteed.',
            ),
          ],
        90 => [
            if (user != null) ...[
              heading(user!.displayName),
              Text(user!.email)
            ],
            heading('Sign out of KoloVibe?'),
            const Text(
              'You’ll need to sign in again to access your profile, Following feed and creator tools. Make sure any upload has completed first.',
            ),
            FilledButton(
              onPressed: busy ? null : logout,
              child: const Text('Sign out'),
            ),
            TextButton(
              onPressed: busy ? null : () => go(79),
              child: const Text('Cancel'),
            ),
          ],
        _ => [],
      };

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: Text(widget.catalog[id].name)),
        body: SafeArea(
          child: loading || busy
              ? const SystemLoading()
              : error != null
                  ? Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        SystemFailureView(
                          error: error!,
                          onRetry: signedOut ? null : load,
                          onSignIn: signedOut ? null : () => go(4, reset: true),
                          onContinue:
                              signedOut ? () => go(2, reset: true) : null,
                          note: signedOut
                              ? 'Signed out on this device. Server session revocation could not be confirmed.'
                              : null,
                        ),
                        if (id == 90 && !signedOut)
                          TextButton(
                            onPressed: logout,
                            child: const Text('Sign out on this device'),
                          ),
                      ],
                    )
                  : ListView(
                      padding: const EdgeInsets.all(24), children: content()),
        ),
      );
}
