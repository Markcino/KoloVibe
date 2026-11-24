import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:kolovibe/app/screen_route.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/core/theme/kolovibe_theme.dart';

import 'audit_harness.dart';
import 'business_harness.dart';

/// A reply for one request: a fixture, an edited copy of one, or a failure.
typedef Reply = ({int status, Map<String, dynamic> body});

Reply fx(String name, [void Function(Map<String, dynamic> body)? edit]) {
  final loaded = fixture(name);
  final body = jsonDecode(jsonEncode(loaded.body)) as Map<String, dynamic>;
  edit?.call(body);
  return (status: loaded.status, body: body);
}

Reply failure(int status,
        [String detail = 'The request could not be completed.']) =>
    (status: status, body: {'detail': detail});

/// Hosts one Business screen with real parsing over a recording fake gateway, and records every navigation.
class ScreenBed {
  ScreenBed(this.harness);
  final BusinessHarness harness;
  final List<ScreenRoute> pushed = [];
  late DesignCatalog catalog;

  static Future<DesignCatalog> loadCatalog() => DesignCatalog.load();

  Future<void> pump(
      WidgetTester tester, Widget Function(DesignCatalog catalog) build,
      {AuditViewport viewport = AuditViewport.standard,
      double textScale = 1}) async {
    catalog = await tester.runAsync(loadCatalog) as DesignCatalog;
    useViewport(tester, viewport, textScale: textScale);
    pushed.clear();
    await tester.pumpWidget(MaterialApp(
        key:
            UniqueKey(), // a fresh app each time, so no screen state survives from an earlier pump
        debugShowCheckedModeBanner: false,
        theme: KoloVibeTheme.light(),
        home: build(catalog),
        onGenerateRoute: (settings) {
          final route = settings.arguments as ScreenRoute?;
          if (route != null) pushed.add(route);
          return MaterialPageRoute<Object?>(
              settings: settings,
              builder: (_) =>
                  Scaffold(body: Text('Destination ${settings.name}')));
        }));
    await settleAsync(tester);
  }

  /// Taps the first widget with [label], scrolling to it first.
  Future<void> tap(WidgetTester tester, String label) async {
    final target = find.text(label).first;
    if (find.text(label).evaluate().isEmpty) {
      // Long lists build their children lazily.
      await tester.scrollUntilVisible(find.text(label), 200,
          scrollable: find.byType(Scrollable).first);
    }
    await tester.ensureVisible(target);
    await tester.pumpAndSettle();
    await tester.tap(target);
    await settleAsync(tester);
  }

  /// Goes back from the last destination page.
  Future<void> back(WidgetTester tester) async {
    tester.state<NavigatorState>(find.byType(Navigator).first).pop();
    await tester.pumpAndSettle();
  }

  /// The last screen navigated to, as `M-nnn` plus its entity.
  String get last =>
      '${pushed.last.name.substring(8)}:${pushed.last.entityId ?? ''}';
}

/// Throws the way a dropped connection does, so the app shows its offline state.
Never offline() => throw http.ClientException('offline');
