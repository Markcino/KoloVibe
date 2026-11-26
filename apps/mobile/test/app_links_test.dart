// Owner decision SIM-02: shared video links open the app at the video.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kolovibe/app/app_dependencies.dart';
import 'package:kolovibe/app/kolovibe_app.dart';
import 'package:kolovibe/app/screen_route.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/features/discovery/live_video_screen.dart';

import 'fl_a_support.dart';

const videoId = '123e4567-e89b-42d3-a456-426614174000';

void main() {
  group('ScreenRoute.fromAppLink', () {
    test('opens the video detail screen for the shared-video path only', () {
      for (final location in [
        '/open/videos/$videoId',
        '/open/videos/$videoId/',
        '/open/videos/${videoId.toUpperCase()}',
        '/open/videos/$videoId?utm_source=chat',
        'https://links.example.test/open/videos/$videoId',
      ]) {
        final route = ScreenRoute.fromAppLink(location);
        expect(route?.screen, 25, reason: location);
        expect(route?.entityId, videoId, reason: location);
      }
    });

    test('ignores every other location', () {
      for (final location in [
        null,
        '',
        '/',
        '/videos/$videoId',
        '/open/videos/not-an-id',
        '/open/videos/$videoId/extra',
        '/open/videos/../creators/$videoId',
        '/open/creators/$videoId',
        '/mobile/M-025',
        '/open/videos/$videoId${'a' * 2048}',
      ]) {
        expect(ScreenRoute.fromAppLink(location), isNull, reason: location);
      }
    });
  });

  group('app link navigation', () {
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

    final videoReads = <String>[];
    Widget app() {
      final client = MockClient((request) async {
        if (request.url.path == '/api/v1/app/compatibility') {
          return jsonResponse({
            'status': 'unknown',
            'minimum_version': null,
            'latest_version': null,
            'store_url': null,
          });
        }
        if (request.url.path.startsWith('/api/v1/videos/')) {
          videoReads.add(request.url.path);
        }
        // The server decides visibility: this video is not public.
        return http.Response('{"detail":"Not found"}', 404,
            headers: {'content-type': 'application/json'});
      });
      addTearDown(client.close);
      return KoloVibeApp(
        catalog: catalog,
        dependencies: AppDependencies.live(
          'https://api.example.test/api/v1',
          credentialStore: MemoryStore(null),
          device: TestDevice(),
          client: client,
        ),
      );
    }

    setUp(videoReads.clear);

    testWidgets('a link that starts the app opens the video above the start',
        (tester) async {
      tester.binding.platformDispatcher.defaultRouteNameTestValue =
          '/open/videos/$videoId';
      addTearDown(
          tester.binding.platformDispatcher.clearDefaultRouteNameTestValue);
      await tester.pumpWidget(app());
      await settle(tester);
      final detail = tester
          .widget<LiveVideoDetailScreen>(find.byType(LiveVideoDetailScreen));
      expect(detail.id, videoId);
      expect(videoReads, contains('/api/v1/videos/$videoId'));
      // The API refused it, so the app shows the unavailable state, not the video.
      expect(find.byKey(const ValueKey('M-031')), findsOneWidget);
      final navigator = tester.state<NavigatorState>(find.byType(Navigator));
      expect(navigator.canPop(), isTrue);
    });

    testWidgets('a link received while running pushes the video',
        (tester) async {
      await tester.pumpWidget(app());
      await settle(tester);
      expect(find.byType(LiveVideoDetailScreen), findsNothing);
      await tester.binding.handlePushRoute('/open/videos/$videoId');
      await settle(tester);
      expect(
          tester
              .widget<LiveVideoDetailScreen>(find.byType(LiveVideoDetailScreen))
              .id,
          videoId);
    });

    testWidgets('an unknown link opens the normal start screen',
        (tester) async {
      tester.binding.platformDispatcher.defaultRouteNameTestValue =
          '/open/videos/not-an-id';
      addTearDown(
          tester.binding.platformDispatcher.clearDefaultRouteNameTestValue);
      await tester.pumpWidget(app());
      await settle(tester);
      expect(find.byType(LiveVideoDetailScreen), findsNothing);
      expect(videoReads, isEmpty);
    });
  });
}
