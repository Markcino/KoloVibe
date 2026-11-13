import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:kolovibe/app/app_dependencies.dart';
import 'package:kolovibe/app/kolovibe_app.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/features/discovery/discovery_catalog_screen.dart';

import 'fl_a_support.dart';

void main() {
  late DesignCatalog catalog;
  setUpAll(() async => catalog = await DesignCatalog.load());

  Future<void> settle(WidgetTester tester) async {
    for (var i = 0; i < 8; i++) {
      await tester.runAsync(
          () => Future<void>.delayed(const Duration(milliseconds: 2)));
      await tester.pump(const Duration(milliseconds: 50));
    }
    await tester.pumpAndSettle();
  }

  for (final failFirstRefresh in [false, true]) {
    testWidgets(
        failFirstRefresh
            ? 'startup retries an unavailable refresh and opens the dashboard'
            : 'startup restores a saved session and opens the dashboard',
        (tester) async {
      final store = MemoryStore();
      var refreshes = 0;
      var accountReads = 0;
      final client = MockClient((request) async {
        switch (request.url.path) {
          case '/api/v1/app/compatibility':
            return jsonResponse({
              'status': 'unknown',
              'minimum_version': null,
              'latest_version': null,
              'store_url': null,
            });
          case '/api/v1/auth/refresh':
            refreshes++;
            if (failFirstRefresh && refreshes == 1) {
              return jsonResponse({}, 503);
            }
            return jsonResponse({
              'access_token': 'access',
              'refresh_token': 'rotated-refresh',
            });
          case '/api/v1/me':
            accountReads++;
            expect(request.headers['authorization'], 'Bearer access');
            return jsonResponse(accountData);
          case '/api/v1/videos':
          case '/api/v1/videos/following':
            return jsonResponse({'items': [], 'next_cursor': null});
          default:
            fail('Unexpected request: ${request.method} ${request.url.path}');
        }
      });
      addTearDown(client.close);
      await tester.pumpWidget(KoloVibeApp(
        catalog: catalog,
        dependencies: AppDependencies.live(
          'https://api.example.test/api/v1',
          credentialStore: store,
          device: TestDevice(),
          client: client,
        ),
      ));
      await settle(tester);

      if (failFirstRefresh) {
        expect(find.byKey(const ValueKey('M-102')), findsOneWidget);
        expect(store.value, 'stored-refresh');
        expect(accountReads, 0);
        await tester.tap(find.widgetWithText(FilledButton, 'Try again'));
        await settle(tester);
      }

      final dashboard = tester
          .widget<DiscoveryCatalogScreen>(find.byType(DiscoveryCatalogScreen));
      expect(dashboard.screen, 17);
      expect(store.value, 'rotated-refresh');
      expect(refreshes, failFirstRefresh ? 2 : 1);
      expect(accountReads, 1);
      expect(find.byKey(const ValueKey('M-102')), findsNothing);
    });
  }
}
