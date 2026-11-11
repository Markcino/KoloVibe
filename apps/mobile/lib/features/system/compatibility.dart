import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../../core/network/api_client.dart';
import '../../core/platform/device_bridge.dart';

/// Startup-only public compatibility policy. Unknown, malformed or failed reads
/// never gate access. Required policies are the only source of a blocking M-108.
class CompatibilityPolicy {
  const CompatibilityPolicy(
    this.status, {
    this.minimum,
    this.latest,
    this.store,
  });
  const CompatibilityPolicy.unknown() : this('unknown');
  final String status;
  final String? minimum, latest;
  final Uri? store;
  bool get required => status == 'update_required';
  bool get available => status == 'update_available';

  factory CompatibilityPolicy.fromJson(Map<String, dynamic> value) {
    final status = value['status'], minimum = value['minimum_version'];
    final latest = value['latest_version'], store = value['store_url'];
    const number = r'(?:0|[1-9][0-9]*)';
    const prerelease = '(?:$number|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)';
    final semver = RegExp(
        '^$number\\.$number\\.$number(?:-$prerelease(?:\\.$prerelease)*)?(?:\\+[0-9a-zA-Z-]+(?:\\.[0-9a-zA-Z-]+)*)?\$');
    if (value.length != 4 ||
        !{
          'unknown',
          'supported',
          'update_available',
          'update_required',
        }.contains(status) ||
        minimum != null &&
            (minimum is! String ||
                minimum.length > 128 ||
                !semver.hasMatch(minimum)) ||
        latest != null &&
            (latest is! String ||
                latest.length > 128 ||
                !semver.hasMatch(latest)) ||
        store != null && store is! String) {
      throw const FormatException('Invalid compatibility policy');
    }
    final url = store is String ? Uri.tryParse(store) : null;
    if (store != null &&
        (url == null ||
            url.scheme != 'https' ||
            url.host.isEmpty ||
            url.userInfo.isNotEmpty ||
            url.port < 1 ||
            url.port > 65535 ||
            (store as String).length > 2048 ||
            RegExp(r'[\s\\]').hasMatch(store))) {
      throw const FormatException('Unsafe app store URL');
    }
    return CompatibilityPolicy(
      status as String,
      minimum: minimum as String?,
      latest: latest as String?,
      store: url,
    );
  }
}

class CompatibilityRepository {
  const CompatibilityRepository(this.api, this.device, {this.platform});
  final ApiClient api;
  final DeviceBridge device;
  final String? platform;

  Future<CompatibilityPolicy> check() async {
    try {
      return await _check().timeout(const Duration(seconds: 2));
    } catch (_) {
      return const CompatibilityPolicy.unknown();
    }
  }

  Future<CompatibilityPolicy> _check() async {
    final selected = platform ??
        switch (defaultTargetPlatform) {
          TargetPlatform.iOS => 'ios',
          TargetPlatform.android => 'android',
          _ => null,
        };
    final version = await device.appVersion();
    if (version == null || !{'ios', 'android'}.contains(selected)) {
      return const CompatibilityPolicy.unknown();
    }
    return CompatibilityPolicy.fromJson(
      await api.request(
        '/app/compatibility',
        query: {'platform': selected!, 'version': version.version},
      ),
    );
  }
}

class CompatibilityScreen extends StatelessWidget {
  const CompatibilityScreen({
    super.key,
    required this.policy,
    required this.device,
    this.onContinue,
    this.onRetry,
  });
  final CompatibilityPolicy policy;
  final DeviceBridge device;
  final VoidCallback? onContinue, onRetry;
  @override
  Widget build(BuildContext context) => PopScope<Object?>(
        canPop: !policy.required,
        child: Scaffold(
          key: const ValueKey('M-108'),
          appBar: AppBar(
            automaticallyImplyLeading: !policy.required,
            title: Text(
              policy.required ? 'Update required' : 'Application compatibility',
            ),
          ),
          body: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  policy.required
                      ? 'Update KoloVibe to continue.'
                      : policy.available
                          ? 'A fresh version is ready.'
                          : 'No required update policy is available.',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                if (policy.minimum != null)
                  Text('Minimum version: ${policy.minimum}'),
                if (policy.latest != null)
                  Text('Latest version: ${policy.latest}'),
                if (policy.store != null)
                  FilledButton(
                    onPressed: () async {
                      final opened = await device.openUrl(policy.store!);
                      if (!context.mounted || opened) return;
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('The app store could not be opened.'),
                        ),
                      );
                    },
                    child: const Text('View in app store'),
                  ),
                if (onRetry != null)
                  TextButton(
                      onPressed: onRetry, child: const Text('Check again')),
                if (!policy.required && onContinue != null)
                  TextButton(
                    onPressed: onContinue,
                    child: const Text('Continue for now'),
                  ),
              ],
            ),
          ),
        ),
      );
}

class OptionalUpdateNotice extends StatelessWidget {
  const OptionalUpdateNotice({
    super.key,
    required this.policy,
    required this.device,
    required this.onDismiss,
  });
  final CompatibilityPolicy policy;
  final DeviceBridge device;
  final VoidCallback onDismiss;
  @override
  Widget build(BuildContext context) => Material(
        child: SafeArea(
          bottom: false,
          child: Padding(
            padding: const EdgeInsets.all(8),
            child: Wrap(
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                const Text('A KoloVibe update is available.'),
                if (policy.store != null)
                  TextButton(
                    onPressed: () async {
                      final opened = await device.openUrl(policy.store!);
                      if (!context.mounted || opened) return;
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('The app store could not be opened.'),
                        ),
                      );
                    },
                    child: const Text('View in app store'),
                  ),
                TextButton(onPressed: onDismiss, child: const Text('Dismiss')),
              ],
            ),
          ),
        ),
      );
}
