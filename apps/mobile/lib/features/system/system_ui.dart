/// Public system presentation API for other features:
/// SystemFailureView maps real failures to M-095/099–103; SystemLoading switches
/// M-097 to M-096 after a request threshold. SystemEmpty is M-098. Wrap editable
/// forms in UnsavedChangesGuard (M-105), use confirmDestructive (M-106) before a
/// real mutation and notifySuccess (M-107) only after acknowledged success.
/// MediaPermissionScreen (M-104) delegates to DeviceBridge; it never infers an OS
/// permission state. No widget in this file manufactures service or user data.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../../core/network/api_client.dart';
import '../../core/platform/device_bridge.dart';
import '../../shared/widgets/kolo_components.dart';

int failureScreen(Object error) {
  if (error is! ApiFailure) return 99;
  if (error.kind == FailureKind.offline) return 95;
  return switch (error.status) {
    401 => 101,
    403 => 100,
    429 => 103,
    503 => 102,
    _ => 99,
  };
}

class SystemFailureView extends StatelessWidget {
  const SystemFailureView({
    super.key,
    required this.error,
    this.onRetry,
    this.onSignIn,
    this.onContinue,
    this.note,
  });
  final Object error;
  final VoidCallback? onRetry, onSignIn, onContinue;
  final String? note;

  @override
  Widget build(BuildContext context) {
    final id = failureScreen(error);
    final title = switch (id) {
      95 => 'No Internet Connection',
      100 => 'Access denied',
      101 => 'Session expired',
      102 => 'Service unavailable',
      103 => 'Rate limit exceeded',
      _ => 'Application error',
    };
    final message = switch (id) {
      95 => 'Check your connection, then try again.',
      100 => 'Your account does not have access to this action.',
      101 => 'Sign in again to continue.',
      102 => 'This service is temporarily unavailable. Please try again.',
      103 => 'Wait before trying again. Repeated requests will not help.',
      _ => 'The request could not be completed. Please try again.',
    };
    final headline = switch (id) {
      95 => 'You’re offline',
      100 => 'You don’t have access to this.',
      101 => 'Let’s reconnect you securely.',
      102 => 'The stage is quiet for a moment.',
      103 => 'A little pause between requests.',
      _ => 'We hit a little offbeat.',
    };
    final icon = switch (id) {
      95 => Icons.wifi_off_outlined,
      100 => Icons.lock_outline,
      101 => Icons.vpn_key_outlined,
      102 => Icons.cloud_off_outlined,
      103 => Icons.timer_outlined,
      _ => Icons.report_problem_outlined,
    };
    return Center(
      child: SingleChildScrollView(
        key: ValueKey('M-${id.toString().padLeft(3, '0')}'),
        padding: const EdgeInsets.all(24),
        child: KoloStatePanel(
          icon: icon,
          label: title,
          headline: headline,
          message: message,
          note: note == null ? null : KoloNote(title: 'Note', message: note!),
          actions: [
            if (id == 101 && onSignIn != null)
              FilledButton(onPressed: onSignIn, child: const Text('Sign in')),
            if (id != 101 && onRetry != null)
              FilledButton(onPressed: onRetry, child: const Text('Try again')),
            if (onContinue != null)
              OutlinedButton(
                onPressed: onContinue,
                child: const Text('Continue to welcome'),
              ),
          ],
        ),
      ),
    );
  }
}

class SystemLoading extends StatefulWidget {
  const SystemLoading({super.key, this.threshold = const Duration(seconds: 3)});
  final Duration threshold;
  @override
  State<SystemLoading> createState() => _SystemLoadingState();
}

class _SystemLoadingState extends State<SystemLoading> {
  Timer? _timer;
  bool _slow = false;
  @override
  void initState() {
    super.initState();
    _timer = Timer(widget.threshold, () {
      if (mounted) setState(() => _slow = true);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Semantics(
        key: ValueKey(_slow ? 'M-096' : 'M-097'),
        liveRegion: true,
        label: _slow
            ? 'Slow Connection. Still waiting for the service.'
            : 'Loading',
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (_slow)
                const Text(
                    'Slow Connection — this is taking longer than usual.'),
              for (var i = 0; i < 3; i++)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: ExcludeSemantics(
                    child: Container(
                      height: 28,
                      decoration: BoxDecoration(
                        color: Theme.of(context)
                            .colorScheme
                            .surfaceContainerHighest,
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
      );
}

class SystemEmpty extends StatelessWidget {
  const SystemEmpty({super.key, this.query = '', this.onEdit});
  final String query;
  final VoidCallback? onEdit;
  @override
  Widget build(BuildContext context) => Padding(
        key: const ValueKey('M-098'),
        padding: const EdgeInsets.symmetric(vertical: 24),
        child: KoloStatePanel(
          icon: Icons.search_off,
          label: 'No search results',
          headline: 'No stories found. Yet.',
          message: query.isEmpty
              ? 'Try a different search.'
              : 'No results for “$query”.',
          actions: [
            if (onEdit != null)
              OutlinedButton(
                  onPressed: onEdit, child: const Text('Edit search')),
          ],
        ),
      );
}

/// The designed confirmation dialog layout: a left-aligned alert mark, a
/// display title, an explanation and stacked actions (a red primary and a soft
/// secondary). Used by the unsaved-changes and destructive confirmations.
Widget _confirmDialog(
  BuildContext dialog, {
  required Key key,
  required String title,
  required String message,
  required String primary,
  required String secondary,
  required bool primaryResult,
}) =>
    AlertDialog(
      key: key,
      scrollable: true,
      icon: Align(
        alignment: Alignment.centerLeft,
        child: SvgPicture.asset(KoloIcons.circleAlert,
            width: 24, height: 24, excludeFromSemantics: true),
      ),
      iconPadding: const EdgeInsets.fromLTRB(24, 24, 24, 0),
      title: Text(title),
      content: Text(message),
      actionsAlignment: MainAxisAlignment.center,
      actionsOverflowDirection: VerticalDirection.down,
      actions: [
        FilledButton(
          onPressed: () => Navigator.pop(dialog, primaryResult),
          child: Text(primary),
        ),
        OutlinedButton(
          onPressed: () => Navigator.pop(dialog, !primaryResult),
          child: Text(secondary),
        ),
      ],
    );

Future<bool> confirmDiscard(BuildContext context) async =>
    await showDialog<bool>(
      context: context,
      builder: (dialog) => _confirmDialog(
        dialog,
        key: const ValueKey('M-105'),
        title: 'Keep your changes?',
        message: 'Leaving discards changes that have not been saved.',
        // Keeping the edits is the safe, primary choice.
        primary: 'Keep editing',
        secondary: 'Discard changes',
        primaryResult: false,
      ),
    ) ??
    false;

class UnsavedChangesGuard extends StatefulWidget {
  const UnsavedChangesGuard({
    super.key,
    required this.dirty,
    required this.child,
    this.busy = false,
    this.onDiscardRoot,
  });
  final bool dirty;
  final bool busy;
  final VoidCallback? onDiscardRoot;
  final Widget child;
  @override
  State<UnsavedChangesGuard> createState() => _UnsavedChangesGuardState();
}

class _UnsavedChangesGuardState extends State<UnsavedChangesGuard> {
  bool _leaving = false, _dialog = false;
  @override
  Widget build(BuildContext context) => PopScope<Object?>(
        canPop: !widget.busy && (!widget.dirty || _leaving),
        onPopInvokedWithResult: (didPop, result) async {
          if (!didPop && widget.busy) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('Please wait for this request to finish.'),
              ),
            );
            return;
          }
          if (didPop || _dialog || !widget.dirty) return;
          _dialog = true;
          final discard = await confirmDiscard(context);
          _dialog = false;
          if (!mounted || !discard) return;
          setState(() => _leaving = true);
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (!mounted) return;
            if (Navigator.of(context).canPop()) {
              Navigator.of(context).pop(result);
            } else {
              widget.onDiscardRoot?.call();
            }
          });
        },
        child: widget.child,
      );
}

Future<bool> confirmDestructive(
  BuildContext context, {
  required String title,
  required String message,
  String confirmLabel = 'Confirm',
}) async =>
    await showDialog<bool>(
      context: context,
      builder: (dialog) => _confirmDialog(
        dialog,
        key: const ValueKey('M-106'),
        title: title,
        message: message,
        primary: confirmLabel,
        secondary: 'Cancel',
        primaryResult: true,
      ),
    ) ??
    false;

void notifySuccess(BuildContext context, String message) =>
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(key: const ValueKey('M-107'), content: Text(message)),
    );

class MediaPermissionScreen extends StatelessWidget {
  const MediaPermissionScreen({super.key, required this.device});
  final DeviceBridge device;
  @override
  Widget build(BuildContext context) => Scaffold(
        key: const ValueKey('M-104'),
        appBar: AppBar(title: const Text('Media permission')),
        body: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: KoloStatePanel(
                icon: Icons.photo_library_outlined,
                label: 'Media permission',
                headline: 'Allow access to your video',
                message: 'Media access is managed in your device settings.',
                actions: [
                  FilledButton(
                    onPressed: () async {
                      final opened = await device.openAppSettings();
                      if (!context.mounted || opened) return;
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text(
                            'App settings are not available on this device.',
                          ),
                        ),
                      );
                    },
                    child: const Text('Open device settings'),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
}

/// Optional official web links. Invalid/unconfigured origins expose no links.
///
/// Owner ruling, 26 November 2026: the only public web pages are the static
/// policies page and the account-deletion request page. No other path is
/// ever linked, so the app cannot point at a product website.
class PublicLinks {
  static const allowedPaths = {'/terms', '/privacy', '/delete-account'};

  PublicLinks(
      [String value =
          const String.fromEnvironment('KOLOVIBE_PUBLIC_WEB_ORIGIN')])
      : origin = _origin(value);
  final Uri? origin;
  static Uri? _origin(String value) {
    try {
      final uri = Uri.tryParse(value);
      if (value.length <= 2048 &&
          uri != null &&
          uri.scheme == 'https' &&
          uri.host.isNotEmpty &&
          uri.port > 0 &&
          uri.port <= 65535 &&
          uri.userInfo.isEmpty &&
          !uri.hasQuery &&
          !uri.hasFragment &&
          {'', '/'}.contains(uri.path) &&
          !RegExp(r'[\s\\]').hasMatch(value)) {
        return uri.replace(path: '');
      }
    } on FormatException {
      return null;
    }
    return null;
  }

  Uri? page(String path) =>
      allowedPaths.contains(path) ? origin?.resolve(path) : null;
}
