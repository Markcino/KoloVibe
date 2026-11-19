import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/app/screen_route.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/core/theme/kolovibe_theme.dart';
import 'package:kolovibe/features/account/account_sessions_screen.dart';
import 'package:kolovibe/features/account/live_account_flow.dart';
import 'package:kolovibe/features/account/live_account_screen.dart';
import 'package:kolovibe/features/settings/live_information_screen.dart';
import 'package:kolovibe/features/settings/live_settings_repository.dart';
import 'package:kolovibe/features/settings/live_settings_screen.dart';
import 'package:kolovibe/features/system/system_ui.dart';
import 'fl_a_support.dart';
import 'support/audit_harness.dart';

/// Renders every live screen at the two audited iPhone sizes and large text,
/// fails on any layout exception, and (with AUDIT_DIR set) writes comparison
/// pictures next to the approved exports:
///
///     AUDIT_DIR=$PWD/build/design-audit flutter test test/design_audit_test.dart
void main() {
  late DesignCatalog catalog;
  setUpAll(() async {
    catalog = await DesignCatalog.load();
    await loadBrandFonts();
  });

  final shot = GlobalKey();
  Widget host(Widget child) => RepaintBoundary(
      key: shot,
      child: MaterialApp(
          key: UniqueKey(),
          debugShowCheckedModeBanner: false,
          theme: KoloVibeTheme.light(),
          home: child,
          onGenerateRoute: (settings) => MaterialPageRoute<void>(
              settings: settings,
              builder: (_) =>
                  Scaffold(body: Text('Destination ${settings.name}')))));

  /// Pumps [build] at every audit configuration. [after] may drive the screen
  /// into a state (open a dialog, scroll) before the picture is taken.
  void audit(String name, int number, Widget Function() build,
      {Future<void> Function(WidgetTester)? after}) {
    for (final viewport in [AuditViewport.standard, AuditViewport.small]) {
      for (final scale in [1.0, 2.0]) {
        testWidgets('$name · ${viewport.name} · text ${scale}x',
            (tester) async {
          useViewport(tester, viewport, textScale: scale);
          await tester.pumpWidget(host(build()));
          await settleAsync(tester);
          if (after != null) await after(tester);
          final error = tester.takeException();
          if (error != null) {
            fail(error is FlutterError ? error.toStringDeep() : '$error');
          }
          if (scale == 1.0) {
            await captureAudit(tester, shot, '${name}_${viewport.name}',
                design: viewport == AuditViewport.standard ? number : null);
          }
        });
      }
    }
  }

  AccountFixture signedIn() => AccountFixture();

  for (final id in [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 16, 80, 82]) {
    audit(
        'M-${id.toString().padLeft(3, '0')}',
        id,
        () => LiveAccountFlowScreen(
            screen: id,
            account: signedIn().account,
            catalog: catalog,
            initialEmail: 'mark@example.test'));
  }
  audit(
      'M-079',
      79,
      () =>
          LiveAccountScreen(repository: signedIn().account, catalog: catalog));
  audit(
      'M-083', 83, () => AccountSessionsScreen(repository: signedIn().account));
  for (final id in [81, 87, 88, 89, 90, 14]) {
    audit(
        'M-${id.toString().padLeft(3, '0')}',
        id,
        () => LiveInformationScreen(
            screen: id,
            catalog: catalog,
            account: signedIn().account,
            device: TestDevice()));
  }
  for (final id in [84, 85, 86, 91, 92, 93, 94]) {
    audit('M-${id.toString().padLeft(3, '0')}', id, () {
      final fixture = signedIn();
      return LiveSettingsScreen(
          route: ScreenRoute(id),
          catalog: catalog,
          repository: LiveSettingsRepository(fixture.account),
          account: fixture.account,
          device: TestDevice());
    });
  }
  for (final entry in {
    95: const ApiFailure(0, 'x', offline: true),
    99: const ApiFailure(500, 'x'),
    100: const ApiFailure(403, 'x'),
    101: const ApiFailure(401, 'x'),
    102: const ApiFailure(503, 'x'),
    103: const ApiFailure(429, 'x'),
  }.entries) {
    audit(
        'M-${entry.key.toString().padLeft(3, '0')}',
        entry.key,
        () => Scaffold(
            body: SafeArea(
                child: Center(
                    child: SystemFailureView(
                        error: entry.value,
                        onRetry: () {},
                        onSignIn: () {})))));
  }
  audit('M-097', 97,
      () => const Scaffold(body: SafeArea(child: SystemLoading())));
  audit(
      'M-098',
      98,
      () => Scaffold(
          body:
              SafeArea(child: SystemEmpty(query: 'Waterside', onEdit: () {}))));
  audit('M-104', 104, () => MediaPermissionScreen(device: TestDevice()));
}
