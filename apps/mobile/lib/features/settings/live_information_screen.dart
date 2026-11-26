import 'package:flutter/material.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/kolo_components.dart';

import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import '../../core/platform/device_bridge.dart';
import '../../core/presentation/design_node.dart';
import '../account/live_account_repository.dart';
import '../legal/legal_screens.dart';
import '../legal/live_legal_repository.dart';
import '../creators/creator_shell.dart';
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

  /// Page titles are 26 pt display text; section titles are 18 pt, as designed.
  static const _sectionTitles = {
    'Your account',
    'Community & support',
    'Respect people',
    'Share responsibly',
    'Honour original work',
    'Keep engagement genuine',
    'In this policy',
    'Popular help topics',
  };
  Widget heading(String value) => Padding(
        padding: EdgeInsets.only(
            top: _sectionTitles.contains(value) ? 16 : 4, bottom: 12),
        child:
            KoloHeadline(value, size: _sectionTitles.contains(value) ? 18 : 26),
      );
  Widget row(String title, int target, [String? subtitle]) => KoloListRow(
        title: title,
        subtitle: subtitle,
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
            // Figma M-014: editorial artwork, headline, role note, two
            // actions. The sample credit line and play button of the export
            // are not drawn: the artwork is static, not a video or a creator.
            ClipRRect(
              borderRadius: BorderRadius.circular(KoloVibeRadii.card),
              child: AspectRatio(
                aspectRatio: 342 / 264,
                child: Stack(fit: StackFit.expand, children: [
                  Image.asset('assets/images/cf426f68e5d77930975f.png',
                      fit: BoxFit.cover, excludeFromSemantics: true),
                  const DecoratedBox(
                      decoration: BoxDecoration(
                          gradient: LinearGradient(
                              begin: Alignment.topCenter,
                              end: Alignment.bottomCenter,
                              colors: [Color(0x21001539), Color(0xF4001539)]))),
                  Positioned(
                    left: 18,
                    right: 18,
                    bottom: 18,
                    child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('CREATOR INTRODUCTION',
                              style: KoloVibeText.body(10,
                                  weight: FontWeight.w700,
                                  color: KoloVibeColors.gold,
                                  letterSpacing: 0.4)),
                          const SizedBox(height: 8),
                          Semantics(
                            header: true,
                            child: Text('Create something only you can.',
                                style: KoloVibeText.heading(27,
                                    color: Colors.white, height: 1.15)),
                          ),
                        ]),
                  ),
                ]),
              ),
            ),
            const SizedBox(height: 16),
            const KoloHeadline('Original starts\nwith you.'),
            const SizedBox(height: 16),
            Text(
              'Share work you own, respect your community and build an authentic audience.',
              style: KoloVibeText.body(14, height: 1.48),
            ),
            const SizedBox(height: 16),
            const KoloNote(
                title: 'Creator access is role-based',
                message:
                    'Complete creator setup. Publishing becomes available when your account is enabled.',
                asset: KoloIcons.info),
            FilledButton(
                onPressed: busy ? null : () => go(36),
                child: const Text('Start creator setup')),
            const SizedBox(height: 12),
            TextButton(
                style: TextButton.styleFrom(
                    minimumSize: const Size.fromHeight(50),
                    textStyle: KoloVibeText.body(14, weight: FontWeight.w700)),
                onPressed: busy ? null : () => go(19),
                child: const Text('Keep exploring')),
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
            if (!terms)
              const Text(
                'Kept on this phone only: recent searches stay on your phone for 14 days, are removed when you sign out, and are never sent to KoloVibe.',
              ),
            const Text(
              'Read the complete, current documents. Available requests and actions depend on applicable policy.',
            ),
            OutlinedButton(
              key: const ValueKey('read-current-document'),
              onPressed: () => openLegalDocument(context,
                  LiveLegalRepository(widget.account), terms ? 'terms' : 'privacy'),
              child: Text(terms
                  ? 'Read the Terms of Service in the app'
                  : 'Read the Privacy Notice in the app'),
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
            row('Video won’t play', 34, 'Connection guidance'),
            row('Upload or review status', 40,
                'Understand your video’s next step'),
            row('Lone Stars explained', 68, 'Non-cash community recognition'),
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
        bottomNavigationBar: creatorNavigation(context, widget.catalog, id),
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
