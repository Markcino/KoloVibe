import 'package:flutter/material.dart';
import '../../core/network/api_client.dart';

/// Reusable loading, empty, offline, expired, restricted, missing, and error
/// states for live screens. Messages never expose raw service details.
class LiveStateView extends StatelessWidget {
  const LiveStateView.loading({super.key, this.label = 'Loading'})
      : title = null,
        message = null,
        icon = null,
        actionLabel = null,
        onAction = null,
        loading = true;

  const LiveStateView.empty({
    super.key,
    required String this.title,
    required String this.message,
    this.icon = Icons.inbox_outlined,
    this.actionLabel,
    this.onAction,
  })  : label = '',
        loading = false;

  const LiveStateView._({
    required String this.title,
    required String this.message,
    required IconData this.icon,
    this.actionLabel,
    this.onAction,
  })  : label = '',
        loading = false;

  /// Maps a failure to the matching state. [onRetry] retries the load;
  /// [onSignIn] is offered when the session expired.
  factory LiveStateView.failure(Object error,
      {Key? key, VoidCallback? onRetry, VoidCallback? onSignIn}) {
    final failure = error is ApiFailure ? error : null;
    return switch (failure?.kind) {
      FailureKind.offline => LiveStateView._(
          title: 'You are offline',
          message: 'Check your connection, then try again.',
          icon: Icons.wifi_off,
          actionLabel: onRetry == null ? null : 'Try again',
          onAction: onRetry),
      FailureKind.expired => LiveStateView._(
          title: 'Session expired',
          message: 'Sign in again to continue.',
          icon: Icons.lock_clock_outlined,
          actionLabel: onSignIn == null ? null : 'Sign in',
          onAction: onSignIn),
      FailureKind.forbidden => LiveStateView._(
          title: 'Not available',
          message: failure!.message,
          icon: Icons.block_outlined),
      FailureKind.notFound => const LiveStateView._(
          title: 'Not found',
          message: 'This item is no longer available.',
          icon: Icons.search_off),
      FailureKind.rateLimited => LiveStateView._(
          title: 'Too many attempts',
          message: 'Wait a moment, then try again.',
          icon: Icons.hourglass_empty,
          actionLabel: onRetry == null ? null : 'Try again',
          onAction: onRetry),
      _ => LiveStateView._(
          title: 'Something went wrong',
          message: failure?.message ?? 'The request could not be completed.',
          icon: Icons.error_outline,
          actionLabel: onRetry == null ? null : 'Try again',
          onAction: onRetry),
    };
  }

  final String label;
  final String? title, message, actionLabel;
  final IconData? icon;
  final VoidCallback? onAction;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    if (loading) {
      return Center(
        child: Semantics(
            label: label,
            liveRegion: true,
            child: const CircularProgressIndicator()),
      );
    }
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Semantics(
          liveRegion: true,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 40, color: theme.colorScheme.primary),
              const SizedBox(height: 12),
              Text(title!,
                  style: theme.textTheme.titleMedium,
                  textAlign: TextAlign.center),
              const SizedBox(height: 6),
              Text(message!,
                  style: theme.textTheme.bodyMedium,
                  textAlign: TextAlign.center),
              if (actionLabel != null && onAction != null) ...[
                const SizedBox(height: 16),
                FilledButton(onPressed: onAction, child: Text(actionLabel!)),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
