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

import '../../core/network/api_client.dart';
import '../../core/platform/device_bridge.dart';

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
    return SingleChildScrollView(
      key: ValueKey('M-${id.toString().padLeft(3, '0')}'),
      padding: const EdgeInsets.all(24),
      child: Semantics(
        liveRegion: true,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.info_outline, size: 40),
            const SizedBox(height: 16),
            Text(title, style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            if (note != null) Text(note!, textAlign: TextAlign.center),
            if (id == 101 && onSignIn != null)
              FilledButton(onPressed: onSignIn, child: const Text('Sign in')),
            if (id != 101 && onRetry != null)
              FilledButton(onPressed: onRetry, child: const Text('Try again')),
            if (onContinue != null)
              TextButton(
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
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.search_off, size: 40),
            const Text('No search results'),
            Text(
              query.isEmpty
                  ? 'Try a different search.'
                  : 'No results for “$query”.',
            ),
            if (onEdit != null)
              TextButton(onPressed: onEdit, child: const Text('Edit search')),
          ],
        ),
      );
}

Future<bool> confirmDiscard(BuildContext context) async =>
    await showDialog<bool>(
      context: context,
      builder: (dialog) => AlertDialog(
        key: const ValueKey('M-105'),
        title: const Text('Keep your changes?'),
        content: const Text(
          'Leaving discards changes that have not been saved.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialog, false),
            child: const Text('Keep editing'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialog, true),
            child: const Text('Discard changes'),
          ),
        ],
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
      builder: (dialog) => AlertDialog(
        key: const ValueKey('M-106'),
        title: Text(title),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialog, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialog, true),
            child: Text(confirmLabel),
          ),
        ],
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
        body: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('Media access is managed in your device settings.'),
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
      );
}

/// Optional official web links. Invalid/unconfigured origins expose no links.
class PublicLinks {
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
      RegExp(r'^/[a-z-]+$').hasMatch(path) ? origin?.resolve(path) : null;
}
