import 'package:flutter/material.dart';
import '../../shared/widgets/kolo_components.dart';

import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import '../../core/platform/device_bridge.dart';
import '../../core/presentation/design_node.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../account/live_account_flow.dart';
import '../creators/creator_shell.dart';
import '../account/live_account_repository.dart';
import '../system/system_ui.dart';
import 'access_export_view.dart';
import 'live_settings_repository.dart';
import '../legal/live_legal_repository.dart';

class LiveSettingsScreen extends StatefulWidget {
  const LiveSettingsScreen({
    super.key,
    required this.route,
    required this.catalog,
    required this.repository,
    required this.account,
    this.device = const PlatformDeviceBridge(),
    this.proof,
    this.receipt,
  });
  final ScreenRoute route;
  final DesignCatalog catalog;
  final LiveSettingsRepository repository;
  final LiveAccountRepository account;
  final DeviceBridge device;
  final Reauthentication? proof;
  final PrivacyReceipt? receipt;
  @override
  State<LiveSettingsScreen> createState() => _LiveSettingsScreenState();
}

class _LiveSettingsScreenState extends State<LiveSettingsScreen> {
  final password = TextEditingController(),
      acknowledgement = TextEditingController();
  bool agreed = false, busy = false, loading = true, dirty = false;
  Object? error;
  String? validation;
  NotificationChoices? choices;
  LegalState? legalState;
  LiveAccount? account;
  List<PrivacyReceipt> receipts = [];
  Reauthentication? proof;
  int get id => widget.route.screen;
  @override
  void initState() {
    super.initState();
    proof = widget.proof;
    load();
  }

  @override
  void dispose() {
    proof?.dispose();
    for (final value in [password, acknowledgement]) {
      value.clear();
      value.dispose();
    }
    super.dispose();
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final user = await widget.account.currentAccount();
      if (user == null) throw const ApiFailure(401, 'Sign in again.');
      account = user;
      if (id == 86) choices = await widget.repository.preferences();
      if (id == 84) {
        // The marketing switch is optional on this screen; privacy requests stay usable if it cannot load.
        try {
          legalState = await LiveLegalRepository(widget.account).state();
        } catch (_) {
          legalState = null;
        }
      }
      if ({93, 94}.contains(id)) {
        receipts = widget.receipt == null
            ? await widget.repository.privacyRequests()
            : [widget.receipt!];
      }
    } catch (failure) {
      error = failure;
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

  Future<void> leave(int target) async {
    if (busy || dirty && !await confirmDiscard(context)) return;
    if (!mounted) return;
    setState(() => dirty = false);
    go(target);
  }

  void showPrivacy(
    int screen, {
    Reauthentication? verified,
    PrivacyReceipt? receipt,
  }) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => LiveSettingsScreen(
          route: ScreenRoute(screen),
          catalog: widget.catalog,
          repository: widget.repository,
          account: widget.account,
          device: widget.device,
          proof: verified,
          receipt: receipt,
        ),
      ),
    );
  }

  Future<void> verifyDeletion() async {
    final verified = await confirmIdentity(
      context,
      widget.account,
      widget.catalog,
    );
    if (!mounted) {
      verified?.dispose();
      return;
    }
    if (verified != null) showPrivacy(92, verified: verified);
  }

  Future<void> saveChoices(NotificationChoices value) async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final saved = await widget.repository.updatePreferences(value);
      if (mounted) {
        choices = saved;
        notifySuccess(context, 'Notification preferences saved.');
      }
    } catch (failure) {
      error = failure;
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  /// Decision B: marketing consent is separate from the terms and the privacy notice, and can be withdrawn any time.
  Future<void> saveMarketing(bool granted) async {
    final current = legalState;
    if (busy || current == null) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final saved = await LiveLegalRepository(widget.account)
          .setMarketing(granted, current.marketingVersion);
      if (mounted) {
        legalState = saved;
        notifySuccess(
            context,
            granted
                ? 'Marketing messages turned on.'
                : 'Marketing messages turned off.');
      }
    } catch (failure) {
      error = failure;
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> submitDeletion() async {
    if (busy) return;
    if (acknowledgement.text.trim() != 'DELETE' ||
        !agreed ||
        proof?.available != true && password.text.isEmpty) {
      setState(
        () => validation =
            'Enter DELETE, acknowledge the policy, and confirm your identity.',
      );
      return;
    }
    setState(() {
      busy = true;
      error = null;
      validation = null;
    });
    PrivacyReceipt? receipt;
    try {
      receipt = proof?.available == true
          ? await widget.repository.requestPrivacyWithProof('deletion', proof!)
          : await widget.repository.requestPrivacy('deletion', password.text);
    } on ApiFailure catch (failure) {
      if (failure.status == 400) {
        validation =
            'Identity confirmation was not accepted. Enter your current password and try again.';
      } else {
        error = failure;
      }
    } catch (failure) {
      error = failure;
    } finally {
      proof?.dispose();
      proof = null;
      password.clear();
      if (mounted) setState(() => busy = false);
    }
    if (!mounted || receipt == null) return;
    setState(() => dirty = false);
    showPrivacy(93, receipt: receipt);
  }

  Future<void> submitAccess() async {
    if (busy) return;
    final verified = await confirmIdentity(
      context,
      widget.account,
      widget.catalog,
    );
    if (!mounted) {
      verified?.dispose();
      return;
    }
    if (verified == null) return;
    setState(() {
      busy = true;
      error = null;
    });
    PrivacyReceipt? receipt;
    try {
      receipt = await widget.repository.requestPrivacyWithProof(
        'access',
        verified,
      );
    } catch (failure) {
      error = failure;
    } finally {
      verified.dispose();
      if (mounted) setState(() => busy = false);
    }
    if (mounted && receipt != null) showPrivacy(94, receipt: receipt);
  }

  /// Mandate 3.3: the account's own completed export, after a fresh identity check; shown in memory only.
  Future<void> viewExport(PrivacyReceipt receipt) async {
    if (busy) return;
    final verified = await confirmIdentity(
      context,
      widget.account,
      widget.catalog,
    );
    if (!mounted) {
      verified?.dispose();
      return;
    }
    if (verified == null) return;
    setState(() {
      busy = true;
      validation = null;
    });
    AccessExport? export;
    try {
      export = await widget.repository.downloadExport(receipt.id, verified);
    } on ApiFailure catch (failure) {
      validation = switch (failure.code) {
        'export_expired' =>
          'This export has expired and was removed. You can request your data again.',
        'export_not_ready' => 'Your data is still being prepared.',
        _ => null,
      };
      if (validation == null) error = failure;
    } catch (failure) {
      error = failure;
    } finally {
      if (mounted) setState(() => busy = false);
    }
    if (!mounted || export == null) return;
    final ready = export;
    await Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => AccessExportView(export: ready),
    ));
  }

  Future<void> openSettings() async {
    final opened = await widget.device.openAppSettings();
    if (!mounted || opened) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('App settings are not available on this device.'),
      ),
    );
  }

  Widget row(String title, int target) =>
      KoloListRow(title: title, onTap: () => leave(target));
  Widget heading(String value) => Padding(
        padding: const EdgeInsets.only(top: 4, bottom: 12),
        child: KoloHeadline(value, size: 26),
      );
  Widget note(String value) => Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Text(value, style: Theme.of(context).textTheme.bodyMedium));
  List<Widget> content() => switch (id) {
        84 => [
            heading('Your data. A clearer view.'),
            note(
              'Understand the information associated with your account and the choices available under the current policy.',
            ),
            row('Account information', 85),
            row('Privacy policy', 88),
            row('Delete account request', 91),
            if (legalState case final legal?)
              SwitchListTile(
                key: const ValueKey('marketing-switch'),
                title: const Text('Marketing messages'),
                subtitle: const Text(
                    'News about new features and offers. Optional, separate from the terms, and never used for advertising or tracking.'),
                value: legal.marketingGranted,
                onChanged: busy ? null : saveMarketing,
              ),
            note(
              'Recent searches stay on your phone, are kept for 14 days, and can be cleared from Search. They are never sent to KoloVibe.',
            ),
            OutlinedButton(
              onPressed: submitAccess,
              child: const Text('Request account data'),
            ),
            row('Your account data request', 94),
            note(
              'Requests are recorded for handling. No data is deleted or exported immediately.',
            ),
          ],
        85 => [
            heading('A safer space for your voice.'),
            const Text('Account email'),
            Text(account!.email),
            row('Change password', 82),
            row('Active sessions', 83),
            note('Never share a password or verification code.'),
          ],
        86 => [
            heading('Stay in the loop. On your terms.'),
            SwitchListTile(
              title: const Text('Email notifications'),
              value: choices!.email,
              onChanged: (v) =>
                  saveChoices(NotificationChoices(v, choices!.push)),
            ),
            SwitchListTile(
              title: const Text('Push notifications'),
              value: choices!.push,
              onChanged: (v) =>
                  saveChoices(NotificationChoices(choices!.email, v)),
            ),
            heading('Device notification permission'),
            note(
              'Permission is managed by your device. Account preferences do not grant device permission.',
            ),
            OutlinedButton(
              onPressed: openSettings,
              child: const Text('Open device settings'),
            ),
            note(
              'Preferences are saved to your account. Notification delivery depends on service availability.',
            ),
          ],
        91 => [
            heading('Before you leave.'),
            note(
              'Deletion requests are reviewed under the applicable account, content and privacy policies.',
            ),
            note(
              'This intake records a request. It does not disable your account or delete data.',
            ),
            FilledButton(
              onPressed: verifyDeletion,
              child: const Text('Verify identity to continue'),
            ),
            OutlinedButton(
              onPressed: () => leave(79),
              child: const Text('Keep my account'),
            ),
          ],
        92 => [
            heading('This is your final confirmation.'),
            Text('Account: ${account!.email}'),
            note(
              proof?.available == true
                  ? 'Identity confirmed for this request.'
                  : 'Confirm your identity with your current password.',
            ),
            note(
              'This records a deletion request. It does not sign you out or delete data now.',
            ),
            TextField(
              controller: acknowledgement,
              decoration: const InputDecoration(
                labelText: 'Type DELETE to acknowledge',
              ),
              autocorrect: false,
              onChanged: (_) => setState(() => dirty = true),
            ),
            if (proof?.available != true)
              TextField(
                controller: password,
                obscureText: true,
                autocorrect: false,
                enableSuggestions: false,
                decoration:
                    const InputDecoration(labelText: 'Current password'),
                onChanged: (_) => setState(() => dirty = true),
              ),
            CheckboxListTile(
              value: agreed,
              onChanged: (v) => setState(() {
                agreed = v ?? false;
                dirty = true;
              }),
              title: const Text(
                'I understand the account and content consequences described in the deletion policy.',
              ),
            ),
            FilledButton(
              onPressed: submitDeletion,
              child: const Text('Confirm deletion request'),
            ),
            OutlinedButton(
              onPressed: () => leave(79),
              child: const Text('Cancel — keep my account'),
            ),
            note(
              'Handling follows the applicable policy. No recovery period is promised.',
            ),
          ],
        93 || 94 => receiptContent(),
        _ => [],
      };
  List<Widget> receiptContent() {
    final matches = receipts.where(
      (r) => r.kind == (id == 93 ? 'deletion' : 'access'),
    );
    if (matches.isEmpty) {
      return [
        heading('Your privacy requests'),
        note('No request of this kind was found for this account.'),
        row('Privacy settings', 84),
      ];
    }
    final receipt = matches.first;
    return [
      const KoloMedallion(KoloIcons.clipboardCheck),
      const SizedBox(height: 24),
      heading(
        receipt.existing
            ? 'Your existing request'
            : 'Your request is recorded.',
      ),
      // The receipt is the service's own record: id, kind, status and time.
      Container(
          width: double.infinity,
          margin: const EdgeInsets.only(bottom: 16),
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(KoloVibeRadii.card)),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            SelectableText('Request ID: ${receipt.id}'),
            const SizedBox(height: 8),
            Text('Kind: ${receipt.kind}'),
            const SizedBox(height: 8),
            Text('Status: ${receipt.status.replaceAll('_', ' ')}'),
            const SizedBox(height: 8),
            Text('Created: ${receipt.createdAt.toUtc().toIso8601String()}'),
          ])),
      if (receipt.kind == 'access' && receipt.status == 'completed') ...[
        FilledButton(
          key: const ValueKey('view-export'),
          onPressed: () => viewExport(receipt),
          child: const Text('View my data'),
        ),
        note(
          'Your data is ready. Confirm your identity to see it. It is available for a limited time.',
        ),
      ] else
        note(
          'This acknowledgment does not mean information has been deleted or exported.',
        ),
      row('Read privacy information', 88),
      row('Return to privacy settings', 84),
    ];
  }

  @override
  Widget build(BuildContext context) => UnsavedChangesGuard(
        dirty: dirty,
        busy: busy,
        onDiscardRoot: () => go(79, reset: true),
        child: Scaffold(
          appBar: AppBar(title: Text(widget.catalog[id].name)),
          bottomNavigationBar: creatorNavigation(context, widget.catalog, id),
          body: SafeArea(
            child: loading || busy
                ? const SystemLoading()
                : error != null
                    ? SystemFailureView(
                        error: error!,
                        onRetry: load,
                        onSignIn: () => go(4, reset: true),
                      )
                    : ListView(
                        padding: const EdgeInsets.all(24),
                        children: [
                          if (validation != null)
                            Semantics(
                                liveRegion: true, child: Text(validation!)),
                          ...content(),
                        ],
                      ),
          ),
        ),
      );
}
