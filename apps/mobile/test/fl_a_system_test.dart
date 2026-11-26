import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/features/system/system_ui.dart';
import 'package:kolovibe/features/system/compatibility.dart';
import 'package:kolovibe/app/app_dependencies.dart';
import 'package:kolovibe/app/kolovibe_app.dart';
import 'fl_a_support.dart';

Map<String, Object?> policy(String status) => {
      'status': status,
      'minimum_version': '1.0.0',
      'latest_version': '2.0.0',
      'store_url': 'https://store.example.test/kolovibe'
    };
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

  for (final item in <Object, int>{
    const ApiFailure(503, '', offline: true): 95,
    const ApiFailure(403, ''): 100,
    const ApiFailure(401, ''): 101,
    const ApiFailure(503, ''): 102,
    const ApiFailure(429, ''): 103,
    StateError('unexpected'): 99
  }.entries) {
    testWidgets('real failure maps to M-${item.value} and retry/sign-in action',
        (tester) async {
      var called = false;
      await tester.pumpWidget(MaterialApp(
          home: Scaffold(
              body: SystemFailureView(
                  error: item.key,
                  onRetry: () => called = true,
                  onSignIn: () => called = true))));
      expect(find.byKey(ValueKey('M-${item.value.toString().padLeft(3, '0')}')),
          findsOneWidget);
      await tester.tap(find.text(item.value == 101 ? 'Sign in' : 'Try again'));
      expect(called, isTrue);
    });
  }
  testWidgets(
      'request threshold turns skeleton into slow connection, timers dispose',
      (tester) async {
    await tester
        .pumpWidget(const MaterialApp(home: Scaffold(body: SystemLoading())));
    expect(find.byKey(const ValueKey('M-097')), findsOneWidget);
    await tester.pump(const Duration(seconds: 3));
    expect(find.byKey(const ValueKey('M-096')), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(seconds: 4));
    expect(tester.takeException(), isNull);
  });
  testWidgets(
      'empty widget uses query and edit callback, no fabricated records',
      (tester) async {
    var edited = false;
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: SystemEmpty(query: 'Liberia', onEdit: () => edited = true))));
    expect(find.text('No results for “Liberia”.'), findsOneWidget);
    await tester.tap(find.text('Edit search'));
    expect(edited, isTrue);
  });
  for (final opens in [true, false]) {
    testWidgets('media permission delegates to native settings, result $opens',
        (tester) async {
      final device = TestDevice()..opens = opens;
      await tester
          .pumpWidget(MaterialApp(home: MediaPermissionScreen(device: device)));
      await tester.tap(find.text('Open device settings'));
      await settle(tester);
      expect(device.settingsCalls, 1);
      expect(find.text('App settings are not available on this device.'),
          opens ? findsNothing : findsOneWidget);
    });
  }
  testWidgets(
      'M-106 destructive dialog requires explicit confirmation, M-107 success acknowledged',
      (tester) async {
    var mutated = false;
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: Builder(
                builder: (context) => TextButton(
                    onPressed: () async {
                      if (!await confirmDestructive(context,
                          title: 'Confirm action?',
                          message: 'End another session.')) {
                        return;
                      }
                      mutated = true;
                      if (context.mounted) {
                        notifySuccess(context, 'Acknowledged by server');
                      }
                    },
                    child: const Text('Start'))))));
    await tester.tap(find.text('Start'));
    await settle(tester);
    await tester.tap(find.text('Cancel'));
    await settle(tester);
    expect(mutated, isFalse);
    await tester.tap(find.text('Start'));
    await settle(tester);
    await tester.tap(find.text('Confirm'));
    await settle(tester);
    expect(mutated, isTrue);
    expect(find.byKey(const ValueKey('M-107')), findsOneWidget);
  });
  test('official links require configured HTTPS origin and fixed safe path',
      () {
    for (final origin in [
      '',
      'http://web.example.test',
      'https://user@web.example.test',
      'https://web.example.test/path',
      'https://web.example.test?query=1',
      'not a URL',
      'https://web.example.test:99999'
    ]) {
      expect(PublicLinks(origin).page('/help'), isNull);
    }
    final links = PublicLinks('https://web.example.test/');
    expect(
        links.page('/privacy').toString(), 'https://web.example.test/privacy');
    expect(links.page('/delete-account').toString(),
        'https://web.example.test/delete-account');
    expect(links.page('//untrusted.example.test'), isNull);
    expect(links.page('/../secret'), isNull);
    // Owner ruling (26 November): nothing beyond the policies and deletion
    // pages, so no help, guidelines or product pages on the web.
    for (final path in ['/help', '/community-guidelines', '/videos', '/']) {
      expect(links.page(path), isNull, reason: path);
    }
  });
  test(
      'compatibility requests installed platform/version and validates response',
      () async {
    final repository = CompatibilityRepository(
        ApiClient('https://api.example.test/api/v1',
            client: MockClient((request) async {
          expect(request.url.path, '/api/v1/app/compatibility');
          expect(request.url.queryParameters,
              {'platform': 'ios', 'version': '1.2.3'});
          expect(request.headers.containsKey('Authorization'), isFalse);
          return jsonResponse(policy('update_required'));
        })),
        TestDevice(),
        platform: 'ios');
    expect((await repository.check()).required, isTrue);
  });
  for (final status in [400, 401, 403, 409, 429, 503, 0]) {
    test('compatibility $status never blocks', () async {
      final repository = CompatibilityRepository(
          ApiClient('https://api.example.test/api/v1',
              client: MockClient((_) async {
            if (status == 0) throw http.ClientException('Offline');
            return jsonResponse({}, status);
          })),
          TestDevice(),
          platform: 'android');
      expect((await repository.check()).status, 'unknown');
    });
  }
  for (final version in ['01.2.3', '1.2.3-01', '1.2.3-..', '1.2.3+.']) {
    test('invalid compatibility semver $version never blocks', () async {
      final repository = CompatibilityRepository(
          ApiClient('https://api.example.test/api/v1',
              client: MockClient((_) async => jsonResponse(
                  {...policy('update_required'), 'minimum_version': version}))),
          TestDevice(),
          platform: 'ios');
      expect((await repository.check()).status, 'unknown');
    });
  }
  for (final bad in [
    <String, Object?>{},
    {...policy('update_required'), 'store_url': 'http://unsafe.test'},
    {...policy('update_required'), 'latest_version': 'bad'},
    {...policy('update_required'), 'extra': true},
    {...policy('update_required'), 'status': 'unrecognised'}
  ]) {
    test('malformed compatibility response never gates', () async {
      final repository = CompatibilityRepository(
          ApiClient('https://api.example.test/api/v1',
              client: MockClient((_) async => jsonResponse(bad))),
          TestDevice(),
          platform: 'ios');
      expect((await repository.check()).required, isFalse);
    });
  }
  testWidgets('compatibility timeout never blocks startup', (tester) async {
    final response = Completer<http.Response>();
    final result = CompatibilityRepository(
            ApiClient('https://api.example.test/api/v1',
                client: MockClient((_) => response.future)),
            TestDevice(),
            platform: 'ios')
        .check();
    await tester.pump();
    await tester.pump(const Duration(seconds: 2));
    expect((await result).status, 'unknown');
    response.complete(jsonResponse(policy('update_required')));
    await tester.pump();
  });
  testWidgets(
      'required compatibility has native store action and no continue action',
      (tester) async {
    final device = TestDevice()..opens = false;
    await tester.pumpWidget(MaterialApp(
        home: CompatibilityScreen(
            policy: CompatibilityPolicy.fromJson(policy('update_required')),
            device: device)));
    expect(find.text('Continue for now'), findsNothing);
    expect(find.byType(BackButton), findsNothing);
    await tester.tap(find.text('View in app store'));
    await settle(tester);
    expect(device.urls.single.scheme, 'https');
    expect(find.text('The app store could not be opened.'), findsOneWidget);
  });
  for (final status in ['update_required', 'update_available', 'unknown']) {
    testWidgets(
        'startup compatibility $status gates or dismisses against live endpoint',
        (tester) async {
      final fixture =
          AccountFixture(handler: (_) async => jsonResponse(policy(status)));
      final deps = AppDependencies.live('https://api.example.test/api/v1',
          credentialStore: fixture.store,
          device: TestDevice(),
          client: fixture.client);
      await tester
          .pumpWidget(KoloVibeApp(dependencies: deps, catalog: catalog));
      await settle(tester);
      if (status == 'update_required') {
        expect(find.byKey(const ValueKey('M-108')), findsOneWidget);
        expect(find.text('Update KoloVibe to continue.'), findsOneWidget);
      } else if (status == 'update_available') {
        expect(find.text('A KoloVibe update is available.'), findsOneWidget);
        await tester.tap(find.text('Dismiss'));
        await settle(tester);
        expect(find.text('A KoloVibe update is available.'), findsNothing);
      } else {
        expect(find.byKey(const ValueKey('M-108')), findsNothing);
      }
      expect(
          fixture.requests
              .any((r) => r.url.path.endsWith('/app/compatibility')),
          isTrue);
    }, variant: TargetPlatformVariant.only(TargetPlatform.android));
  }
  testWidgets(
      'startup rejected saved refresh goes to session expired and sign-in',
      (tester) async {
    final store = MemoryStore();
    final client =
        MockClient((request) async => request.url.path.endsWith('/auth/refresh')
            ? jsonResponse({}, 401)
            : jsonResponse({
                'status': 'unknown',
                'minimum_version': null,
                'latest_version': null,
                'store_url': null
              }));
    await tester.pumpWidget(KoloVibeApp(
        catalog: catalog,
        dependencies: AppDependencies.live('https://api.example.test/api/v1',
            credentialStore: store, device: TestDevice(), client: client)));
    await settle(tester);
    expect(find.byKey(const ValueKey('M-101')), findsOneWidget);
    expect(store.value, isNull);
    await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
    await settle(tester);
    expect(find.byKey(const ValueKey('live-M-004')), findsOneWidget);
  });
}
