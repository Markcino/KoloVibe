import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:video_player/video_player.dart';
import 'package:kolovibe/app/screen_route.dart';
import 'package:kolovibe/app/app_dependencies.dart';
import 'package:kolovibe/app/app_session.dart';
import 'package:kolovibe/app/routes/route_context.dart';
import 'package:kolovibe/app/routes/discovery_routes.dart';
import 'package:kolovibe/features/discovery/vertical_video_feed.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/features/account/live_account_repository.dart';
import 'package:kolovibe/features/discovery/discovery_catalog_screen.dart';
import 'package:kolovibe/features/discovery/live_video_repository.dart';
import 'package:kolovibe/features/discovery/live_video_screen.dart';
import 'package:kolovibe/features/creators/live_creator_repository.dart';
import 'package:kolovibe/features/creators/live_creator_screen.dart';
import 'package:kolovibe/features/engagement/live_video_engagement_repository.dart';
import 'fl_a_support.dart';
import 'fl_b_repositories_test.dart'
    show videoJson, creatorJson, playbackJson, videoId;

class CatalogFixture extends LiveVideoRepository {
  CatalogFixture(this.fetch)
      : super(ApiClient('https://api.example.test/api/v1'));
  final Future<LiveVideoPage> Function(Map<String, String?>) fetch;
  @override
  Future<LiveVideoPage> filteredPage(
          {String? cursor,
          String? creatorId,
          String? query,
          String? category,
          String sort = 'recent'}) =>
      fetch({
        'cursor': cursor,
        'creator_id': creatorId,
        'q': query,
        'category': category,
        'sort': sort
      });
  @override
  Future<LiveVideoPage> followingPage(LiveAccountRepository account,
          {String? cursor}) =>
      fetch({'cursor': cursor, 'following': 'true'});
}

class PlayerFixture extends LiveVideoRepository {
  PlayerFixture() : super(ApiClient('https://api.example.test/api/v1'));
  Object? failure;
  int grants = 0;
  @override
  Future<LiveVideo> detail(String id) async {
    if (failure != null) throw failure!;
    return LiveVideo.fromJson(videoJson(id));
  }

  @override
  Future<PlaybackGrant> playback(String id,
      {LiveAccountRepository? account}) async {
    grants++;
    if (failure != null) throw failure!;
    return PlaybackGrant.fromJson(playbackJson(), tracked: false);
  }
}

class FakePlayer extends VideoPlayerController {
  FakePlayer()
      : super.networkUrl(Uri.parse('https://media.example.test/video'));
  bool disposed = false;
  bool fail = false;
  Completer<void>? pending;
  @override
  Future<void> initialize() async {
    if (pending != null) await pending!.future;
    if (fail) throw StateError('Media failed');
    value = const VideoPlayerValue(
        duration: Duration(seconds: 30),
        size: Size(360, 640),
        isInitialized: true);
  }

  @override
  Future<void> play() async => value = value.copyWith(isPlaying: true);
  @override
  Future<void> pause() async {
    if (!disposed) value = value.copyWith(isPlaying: false);
  }

  @override
  Future<void> dispose() async {
    disposed = true;
    await super.dispose();
  }
}

Future<void> settle(WidgetTester tester) async {
  for (var i = 0; i < 8; i++) {
    await tester
        .runAsync(() => Future<void>.delayed(const Duration(milliseconds: 2)));
    await tester.pump(const Duration(milliseconds: 50));
  }
  await tester.pumpAndSettle();
}

Widget app(Widget child) => MaterialApp(
    key: UniqueKey(),
    home: child,
    onGenerateRoute: (settings) => MaterialPageRoute<void>(
        settings: settings,
        builder: (_) => Scaffold(
            body: Text('Destination ${settings.name}',
                key: ValueKey<String>(
                    (settings.arguments as ScreenRoute?)?.entityId ??
                        'none')))));
Future<void> tap(WidgetTester tester, String label) async {
  final buttons = find.ancestor(
      of: find.text(label),
      matching: find.byWidgetPredicate((w) => w is ButtonStyleButton));
  final target =
      buttons.evaluate().isEmpty ? find.text(label).last : buttons.last;
  await tester.ensureVisible(target);
  await tester.tap(target);
  await settle(tester);
}

void main() {
  late DesignCatalog catalog;
  setUpAll(() async => catalog = await DesignCatalog.load());
  for (final screen in [17, 18, 19, 20, 22, 27]) {
    testWidgets(
        'M-$screen reads actual section/filter feed and empties honestly',
        (tester) async {
      final calls = <Map<String, String?>>[];
      final fixture = CatalogFixture((query) async {
        calls.add(query);
        return const LiveVideoPage([], null);
      });
      await tester.pumpWidget(app(DiscoveryCatalogScreen(
          screen: screen,
          repository: fixture,
          catalog: catalog,
          account: AccountFixture().account,
          creatorId: screen == 27 ? accountId : null)));
      await settle(tester);
      if (screen == 17) {
        // Trending and following; the greeting never carries a fixed name.
        expect(calls.length, 2);
        expect(find.text('No trending originals yet'), findsOneWidget);
      } else if (screen == 20) {
        expect(calls.single['sort'], 'trending');
      } else if (screen == 18) {
        expect(calls.single['following'], 'true');
      } else if (screen == 27) {
        expect(calls.single['creator_id'], accountId);
      }
      expect(find.textContaining('Ama'), findsNothing);
    });
  }
  testWidgets(
      'following signed-out prompts sign-in, never public-list fallback',
      (tester) async {
    final fixture = CatalogFixture(
        (_) async => throw StateError('Must not read public list'));
    await tester.pumpWidget(app(DiscoveryCatalogScreen(
        screen: 18, repository: fixture, catalog: catalog)));
    await settle(tester);
    await tap(tester, 'Sign in');
    expect(find.text('Destination /mobile/M-004'), findsOneWidget);
  });
  testWidgets(
      'explore category selection queries real category and clear resets it',
      (tester) async {
    final calls = <Map<String, String?>>[];
    final fixture = CatalogFixture((q) async {
      calls.add(q);
      return const LiveVideoPage([], null);
    });
    await tester.pumpWidget(app(DiscoveryCatalogScreen(
        screen: 19, repository: fixture, catalog: catalog)));
    await settle(tester);
    await tester.tap(find.widgetWithText(ChoiceChip, 'Hipco'));
    await settle(tester);
    expect(calls.last['category'], 'hipco');
    await tester.tap(find.widgetWithText(ChoiceChip, 'All'));
    await settle(tester);
    expect(calls.last['category'], isNull);
  });
  testWidgets('search entry shows a hint, not an empty-catalogue claim',
      (tester) async {
    final calls = <Map<String, String?>>[];
    final fixture = CatalogFixture((q) async {
      calls.add(q);
      return const LiveVideoPage([], null);
    });
    await tester.pumpWidget(app(DiscoveryCatalogScreen(
        screen: 21, repository: fixture, catalog: catalog)));
    await settle(tester);
    expect(calls, isEmpty, reason: 'nothing is requested before a search');
    expect(find.text('Find original videos and the creators behind them.'),
        findsOneWidget);
    expect(find.text('Nothing here yet'), findsNothing);
    expect(find.text('No originals are available yet.'), findsNothing);
  });
  for (final screen in [21, 22, 23]) {
    testWidgets(
        'M-$screen search, no results and category filters use live query',
        (tester) async {
      final calls = <Map<String, String?>>[];
      final fixture = CatalogFixture((q) async {
        calls.add(q);
        return const LiveVideoPage([], null);
      });
      await tester.pumpWidget(app(DiscoveryCatalogScreen(
          screen: screen, repository: fixture, catalog: catalog)));
      await settle(tester);
      await tester.enterText(find.byType(TextField), 'Waterside');
      await tester.testTextInput.receiveAction(TextInputAction.search);
      await settle(tester);
      expect(calls.last['q'], 'Waterside');
      expect(find.byKey(const ValueKey('M-098')), findsOneWidget);
      await tester.tap(find.byTooltip('Filters'));
      await settle(tester);
      await tester.tap(find.widgetWithText(ChoiceChip, 'Culture'));
      await tap(tester, 'Apply category');
      expect(calls.last['category'], 'culture');
      expect(calls.last['q'], 'Waterside');
    });
  }
  testWidgets('paging retains records after outage and retries the same cursor',
      (tester) async {
    // A tall surface keeps the hero card and the retry control on screen.
    tester.view.physicalSize = const Size(800, 3200);
    tester.view.devicePixelRatio = 2;
    addTearDown(tester.view.reset);
    var fail = true;
    final calls = <String?>[];
    final fixture = CatalogFixture((q) async {
      calls.add(q['cursor']);
      if (q['cursor'] == receiptId) {
        if (fail) throw const ApiFailure(503, 'Unavailable');
        return LiveVideoPage([LiveVideo.fromJson(videoJson())], null);
      }
      return LiveVideoPage(
          [LiveVideo.fromJson(videoJson(receiptId))], receiptId);
    });
    await tester.pumpWidget(app(DiscoveryCatalogScreen(
        screen: 20, repository: fixture, catalog: catalog)));
    await settle(tester);
    await tap(tester, 'Load more videos');
    expect(find.text('Waterside'), findsOneWidget);
    fail = false;
    await tap(tester, 'Try again');
    expect(calls, [null, receiptId, receiptId]);
    expect(find.text('Waterside'), findsNWidgets(2));
  });
  for (final status in [401, 403, 404, 409, 429, 503, 0]) {
    testWidgets('catalog failure $status is typed and retryable',
        (tester) async {
      final fixture = CatalogFixture((_) async => throw ApiFailure(
          status == 0 ? 503 : status, 'Failure',
          offline: status == 0));
      await tester.pumpWidget(app(DiscoveryCatalogScreen(
          screen: 20, repository: fixture, catalog: catalog)));
      await settle(tester);
      final id = {401: 101, 403: 100, 429: 103, 503: 102, 0: 95}[status] ?? 99;
      expect(find.byKey(ValueKey('M-${id.toString().padLeft(3, '0')}')),
          findsOneWidget);
    });
    testWidgets(
        'video metadata failure $status maps restricted/unavailable/system state',
        (tester) async {
      final fixture = PlayerFixture()
        ..failure = ApiFailure(status == 0 ? 503 : status, 'Failure',
            offline: status == 0);
      await tester.pumpWidget(
          app(LiveVideoDetailScreen(id: videoId, repository: fixture)));
      await settle(tester);
      if (status == 401) {
        await tap(tester, 'Sign in to watch');
        expect(find.text('Destination /mobile/M-004'), findsOneWidget);
      } else {
        final id = {
              403: 'M-035',
              404: 'M-031',
              429: 'M-103',
              503: 'M-102',
              0: 'M-095'
            }[status] ??
            'M-099';
        expect(find.byKey(ValueKey(id)), findsOneWidget);
      }
    });
  }
  testWidgets(
      'public creator data and follow optimistic rollback preserve server counts',
      (tester) async {
    final pending = Completer<http.Response>();
    final fixture = AccountFixture(handler: (request) async {
      if (request.method == 'PUT') return pending.future;
      return jsonResponse(
          {'creator_id': accountId, 'following': false, 'follower_count': 7});
    });
    final creators = LiveCreatorRepository(
        ApiClient('https://api.example.test/api/v1', client: fixture.client));
    // Public detail uses the fixture's independent public HTTP response.
    final profile = CreatorFixture(creators.api);
    await tester.pumpWidget(app(LiveCreatorScreen(
        id: accountId, repository: profile, account: fixture.account)));
    await settle(tester);
    expect(find.text('@mark · Monrovia'), findsOneWidget);
    expect(find.bySemanticsLabel('Published videos 2'), findsOneWidget);
    await tap(tester, 'Follow Mark');
    expect(find.text('Following'), findsOneWidget);
    expect(find.bySemanticsLabel('Followers 8'), findsOneWidget);
    pending.complete(jsonResponse({}, 503));
    await settle(tester);
    expect(find.text('Follow Mark'), findsOneWidget);
    expect(find.bySemanticsLabel('Followers 7'), findsOneWidget);
    await tap(tester, 'See all videos');
    expect(find.text('Destination /mobile/M-027'), findsOneWidget);
    expect(find.byKey(const ValueKey(accountId)), findsOneWidget);
  });
  testWidgets(
      'native share records then delegates real URL; creator/report routing uses ids',
      (tester) async {
    final device = ShareDevice();
    final fixture = AccountFixture(
        handler: (request) async => request.url.path.endsWith('/shares')
            ? jsonResponse({
                'video_id': videoId,
                'share_url': 'https://web.example.test/videos/$videoId'
              })
            : jsonResponse(
                {'video_id': videoId, 'liked': false, 'like_count': 12}));
    await tester.pumpWidget(app(LiveVideoDetailScreen(
        id: videoId,
        repository: PlayerFixture(),
        engagement: LiveVideoEngagementRepository(fixture.account),
        device: device)));
    await settle(tester);
    await tap(tester, 'Share');
    // The recorded share opens the designed sheet; nothing is shared until the
    // person chooses a destination.
    expect(find.text('Share original stories'), findsOneWidget);
    expect(device.shared, isEmpty);
    await tap(tester, 'Share link using a device app');
    expect(device.shared, ['https://web.example.test/videos/$videoId']);
    expect(device.urls, isEmpty);
    await tap(tester, 'Share');
    await tap(tester, 'Copy public link');
    expect(find.text('Public link copied'), findsOneWidget);
    expect(device.shared.length, 1);
    await tap(tester, 'View creator');
    expect(find.text('Destination /mobile/M-026'), findsOneWidget);
    expect(find.byKey(const ValueKey(accountId)), findsOneWidget);
  });

  testWidgets(
      'watch progress comes from actual player positions; like count uses server result',
      (tester) async {
    final events = <String>[];
    final fixture = AccountFixture(handler: (request) async {
      if (request.url.path.endsWith('/watch-sessions')) {
        return jsonResponse({
          'session_id': receiptId,
          'session_expires_at': proofData['expires_at'],
          'playback_url': playbackJson()['playback_url'],
          'playback_expires_at': playbackJson()['expires_at']
        });
      }
      if (request.url.path.endsWith('/watch-events')) {
        events.add(request.body);
        return jsonResponse({'qualified': false});
      }
      return jsonResponse({
        'video_id': videoId,
        'liked': request.method == 'PUT',
        'like_count': request.method == 'PUT' ? 13 : 12
      });
    });
    final player = FakePlayer();
    await tester.pumpWidget(app(LiveVideoDetailScreen(
        id: videoId,
        repository: PlayerFixture(),
        engagement: LiveVideoEngagementRepository(fixture.account),
        playerFactory: (_) => player)));
    await settle(tester);
    await tap(tester, 'Like');
    expect(find.text('13 likes'), findsOneWidget);
    await tap(tester, 'Play original');
    player.value = player.value.copyWith(position: const Duration(seconds: 3));
    await settle(tester);
    expect(events.length, 1);
    expect(events.single, contains('"position_ms":3000'));
    expect(events.single, isNot(contains('qualified')));
    expect(events.single, isNot(contains('points')));
    await tester.pumpWidget(const SizedBox());
    await settle(tester);
    expect(player.disposed, isTrue);
  });
  for (final status in [401, 403, 404, 409, 429, 503, 0]) {
    for (final action in ['like', 'share', 'follow']) {
      testWidgets(
          '$action failure $status is honest and does not retain optimistic changes',
          (tester) async {
        final device = ShareDevice();
        final fixture = AccountFixture(handler: (request) async {
          if (request.method == 'GET') {
            return action == 'follow'
                ? jsonResponse({
                    'creator_id': accountId,
                    'following': false,
                    'follower_count': 7
                  })
                : jsonResponse(
                    {'video_id': videoId, 'liked': false, 'like_count': 12});
          }
          if (status == 0) throw http.ClientException('Offline');
          return jsonResponse(
              {'detail': 'Unavailable', 'code': 'share_unavailable'}, status);
        });
        await tester.pumpWidget(app(action == 'follow'
            ? LiveCreatorScreen(
                id: accountId,
                repository: CreatorFixture(fixture.account.api),
                account: fixture.account)
            : LiveVideoDetailScreen(
                id: videoId,
                repository: PlayerFixture(),
                engagement: LiveVideoEngagementRepository(fixture.account),
                device: device)));
        await settle(tester);
        await tap(
            tester,
            action == 'like'
                ? 'Like'
                : action == 'follow'
                    ? 'Follow Mark'
                    : 'Share');
        if (status == 401) {
          expect(find.text('Destination /mobile/M-004'), findsOneWidget);
        } else if (action == 'follow') {
          expect(find.text('Follow Mark'), findsOneWidget);
          expect(find.bySemanticsLabel('Followers 7'), findsOneWidget);
        } else if (action == 'like') {
          expect(find.text('Like'), findsOneWidget);
          expect(find.text('12 likes'), findsOneWidget);
        } else {
          expect(
              find.text(
                  'Sharing is unavailable right now. No share link was opened.'),
              findsOneWidget);
        }
        expect(device.shared, isEmpty);
      });
    }
  }

  for (final status in [401, 403, 404, 409, 429, 503, 0]) {
    testWidgets(
        'initial follow state failure $status preserves public profile and shows recovery',
        (tester) async {
      final fixture = AccountFixture(handler: (_) async {
        if (status == 0) throw http.ClientException('Offline');
        return jsonResponse({}, status);
      });
      await tester.pumpWidget(app(LiveCreatorScreen(
          id: accountId,
          repository: CreatorFixture(fixture.account.api),
          account: fixture.account)));
      await settle(tester);
      expect(find.text('@mark · Monrovia'), findsOneWidget);
      if (status == 401) {
        await tap(tester, 'Follow Mark');
        expect(find.text('Destination /mobile/M-004'), findsOneWidget);
      } else {
        final id = {
              403: 'M-100',
              429: 'M-103',
              503: 'M-102',
              0: 'M-095'
            }[status] ??
            'M-099';
        expect(find.byKey(ValueKey(id)), findsOneWidget);
      }
    });
  }
  test('public creator routing leaves route 38 to the owner studio', () {
    final deps = AppDependencies.live('https://api.example.test/api/v1');
    final session = AppSession();
    expect(
        discoveryRoute(RouteContext(
            route: const ScreenRoute(38, entityId: accountId),
            catalog: catalog,
            dependencies: deps,
            session: session)),
        isNull);
    final public = discoveryRoute(RouteContext(
        route: const ScreenRoute(26, entityId: accountId),
        catalog: catalog,
        dependencies: deps,
        session: session));
    expect(public, isA<LiveCreatorScreen>());
    expect((public as LiveCreatorScreen).id, accountId);
    session.dispose();
  });
  testWidgets(
      'vertical swipe disposes previous player and only plays visible item',
      (tester) async {
    final players = <FakePlayer>[];
    await tester.pumpWidget(app(VerticalVideoFeed(
        repository: FeedFixture(),
        device: ShareDevice(),
        playerFactory: (_) {
          final player = FakePlayer();
          players.add(player);
          return player;
        })));
    await settle(tester);
    expect(players.length, 1);
    expect(players.first.value.isPlaying, isTrue);
    await tester.drag(find.byType(PageView), const Offset(0, -650));
    await settle(tester);
    expect(players.length, 2);
    expect(players.first.disposed, isTrue);
    expect(players.last.value.isPlaying, isTrue);
    await tester.tap(find.byTooltip('More'));
    await settle(tester);
    await tap(tester, 'Report video');
    expect(players.last.value.isPlaying, isFalse);
    expect(find.text('Destination /mobile/M-004'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
    await settle(tester);
    expect(players.last.disposed, isTrue);
  });
  testWidgets('report entry carries video id to FL-D route 71', (tester) async {
    final fixture = AccountFixture(
        handler: (_) async => jsonResponse(
            {'video_id': videoId, 'liked': false, 'like_count': 12}));
    await tester.pumpWidget(app(LiveVideoDetailScreen(
        id: videoId,
        repository: PlayerFixture(),
        engagement: LiveVideoEngagementRepository(fixture.account))));
    await settle(tester);
    await tap(tester, 'Report this video');
    expect(find.text('Destination /mobile/M-071'), findsOneWidget);
    expect(find.byKey(const ValueKey(videoId)), findsOneWidget);
  });
  testWidgets(
      'buffering threshold, playback error retry and disposal use real controller states',
      (tester) async {
    final repository = PlayerFixture();
    final first = FakePlayer()..pending = Completer<void>();
    final second = FakePlayer();
    var attempts = 0;
    await tester.pumpWidget(app(LiveVideoDetailScreen(
        id: videoId,
        repository: repository,
        fullScreen: true,
        playerFactory: (_) => attempts++ == 0 ? first : second)));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.byKey(const ValueKey('M-032')), findsOneWidget);
    await tester.pump(const Duration(seconds: 5));
    expect(find.byKey(const ValueKey('M-034')), findsOneWidget);
    first.fail = true;
    first.pending!.complete();
    await settle(tester);
    expect(find.byKey(const ValueKey('M-033')), findsOneWidget);
    await tap(tester, 'Retry playback');
    expect(attempts, 2);
    expect(repository.grants, 2);
    expect(first.disposed, isTrue);
    await tester.pumpWidget(const SizedBox());
    await settle(tester);
    expect(second.disposed, isTrue);
  });
}

class CreatorFixture extends LiveCreatorRepository {
  const CreatorFixture(super.api);
  @override
  Future<LiveCreator> detail(String id) async =>
      LiveCreator.fromJson(creatorJson());
}

class ShareDevice extends TestDevice {
  final shared = <String>[];
  @override
  Future<bool> share(String text) async {
    shared.add(text);
    return true;
  }
}

class FeedFixture extends PlayerFixture {
  @override
  Future<LiveVideoPage> page(
          {String? cursor, String? creatorId, String? query}) async =>
      LiveVideoPage([
        LiveVideo.fromJson(videoJson()),
        LiveVideo.fromJson(videoJson(receiptId))
      ], null);
}
