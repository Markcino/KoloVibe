import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/app/screen_route.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/core/theme/kolovibe_theme.dart';
import 'package:kolovibe/features/creators/live_creator_repository.dart';
import 'package:kolovibe/features/discovery/discovery_catalog_screen.dart';
import 'package:kolovibe/features/discovery/home_dashboard.dart';
import 'package:kolovibe/features/discovery/live_video_repository.dart';
import 'fl_a_support.dart';
import 'fl_b_repositories_test.dart' show videoJson, creatorJson;
import 'support/audit_harness.dart';

const heroCreatorId = '00000000-0000-4000-8000-0000000000a1';
const otherVideoId = '00000000-0000-4000-8000-000000000004';
const otherCreatorId = '00000000-0000-4000-8000-0000000000a2';

class HomeVideos extends LiveVideoRepository {
  HomeVideos({this.trending, this.following})
      : super(ApiClient('https://api.example.test/api/v1'));
  final Future<LiveVideoPage> Function()? trending, following;
  int trendingCalls = 0, followingCalls = 0;
  @override
  Future<LiveVideoPage> filteredPage(
      {String? cursor,
      String? creatorId,
      String? query,
      String? category,
      String sort = 'recent'}) {
    expect(sort, 'trending');
    trendingCalls++;
    return (trending ?? () async => const LiveVideoPage([], null))();
  }

  @override
  Future<LiveVideoPage> followingPage(account, {String? cursor}) {
    followingCalls++;
    return (following ?? () async => const LiveVideoPage([], null))();
  }
}

class HomeCreators extends LiveCreatorRepository {
  HomeCreators({this.fail = false})
      : super(ApiClient('https://api.example.test/api/v1'));
  final bool fail;
  @override
  Future<LiveCreator> detail(String id) async {
    if (fail) throw const ApiFailure(503, 'down');
    return LiveCreator.fromJson({
      ...creatorJson(),
      'id': id,
      'handle': id == otherCreatorId ? 'jslay' : 'esikollie',
      'display_name': id == otherCreatorId ? 'J Slay' : 'Esi Kollie',
    });
  }
}

LiveVideoPage twoVideos() => LiveVideoPage([
      LiveVideo.fromJson({
        ...videoJson(),
        'creator_id': heroCreatorId,
        'title': 'Waterside at dawn',
        'category': 'short_films',
      }),
      LiveVideo.fromJson({
        ...videoJson(otherVideoId),
        'creator_id': otherCreatorId,
        'title': 'City lights, fresh bars',
        'category': 'hipco',
        'like_count': 8600,
      }),
    ], null);

void main() {
  late DesignCatalog catalog;
  setUpAll(() async {
    catalog = await DesignCatalog.load();
    await loadBrandFonts();
  });

  final destinations = <String>[];
  final shot = GlobalKey();
  Widget host(Widget child) => RepaintBoundary(
      key: shot,
      child: MaterialApp(
          key: UniqueKey(),
          debugShowCheckedModeBanner: false,
          theme: KoloVibeTheme.light(),
          home: child,
          onGenerateRoute: (settings) {
            destinations.add(
                '${settings.name}:${(settings.arguments as ScreenRoute?)?.entityId ?? ''}');
            return MaterialPageRoute<void>(
                settings: settings,
                builder: (_) =>
                    Scaffold(body: Text('Destination ${settings.name}')));
          }));

  AccountFixture signedIn({
    bool followed = false,
    Future<dynamic> Function(String method)? onFollow,
    Map<String, Object?>? me,
  }) =>
      AccountFixture(handler: (request) async {
        if (request.url.path.contains('/follow')) {
          final id =
              request.url.pathSegments[request.url.pathSegments.length - 2];
          if (request.method != 'GET' && onFollow != null) {
            return await onFollow(request.method);
          }
          return jsonResponse({
            'creator_id': id,
            'following': request.method == 'PUT'
                ? true
                : request.method == 'DELETE'
                    ? false
                    : followed,
            'follower_count': 7
          });
        }
        return jsonResponse({});
      });

  Future<void> pumpHome(
    WidgetTester tester, {
    required HomeVideos videos,
    HomeCreators? creators,
    AccountFixture? account,
    AuditViewport viewport = AuditViewport.standard,
    double textScale = 1,
    double keyboard = 0,
  }) async {
    useViewport(tester, viewport, textScale: textScale, keyboard: keyboard);
    destinations.clear();
    await tester.pumpWidget(host(DiscoveryCatalogScreen(
        screen: 17,
        repository: videos,
        catalog: catalog,
        creators: creators ?? HomeCreators(),
        account: account?.account)));
    await settleAsync(tester);
  }

  Future<void> tapText(WidgetTester tester, String text) async {
    final target = find.text(text).first;
    await tester.ensureVisible(target);
    await tester.pumpAndSettle();
    await tester.tap(target);
    await settleAsync(tester);
  }

  group('signed in with real data', () {
    testWidgets('shows the real name, hero, creators, trending and chips',
        (tester) async {
      final videos = HomeVideos(trending: () async => twoVideos());
      await pumpHome(tester, videos: videos, account: signedIn());
      await captureAudit(tester, shot, 'M-017_390x844', design: 17);
      expect(find.textContaining('Mark'), findsWidgets);
      expect(find.textContaining('Ama'), findsNothing);
      expect(find.text('Waterside at dawn'), findsOneWidget);
      expect(find.text('Esi Kollie · Short films'), findsOneWidget);
      expect(find.text('KOLOVIBE ORIGINAL'), findsOneWidget);
      expect(find.text('City lights, fresh bars'), findsOneWidget);
      expect(find.text('J Slay · Hipco · 8.6K likes'), findsOneWidget);
      expect(find.text('Creators to know'), findsOneWidget);
      expect(find.text('Esi Kollie'), findsOneWidget);
      expect(find.text('@esikollie · Monrovia'), findsOneWidget);
      expect(find.text('Follow'), findsWidgets);
      for (final label in ['Home', 'Explore', 'Create', 'Videos', 'Profile']) {
        expect(find.text(label), findsWidgets);
      }
      expect(videos.trendingCalls, 1);
      noException(tester);
    });

    testWidgets('a different account name is shown, never a fixed one',
        (tester) async {
      final fixture = AccountFixture();
      accountData['display_name'] = 'Kofi Mensah';
      addTearDown(() => accountData['display_name'] = 'Mark');
      await pumpHome(tester,
          videos: HomeVideos(trending: () async => twoVideos()),
          account: fixture);
      expect(find.textContaining('Kofi Mensah'), findsOneWidget);
      expect(find.textContaining('Mark'), findsNothing);
    });

    testWidgets('own creator profile is not suggested for following',
        (tester) async {
      final own = LiveVideoPage([
        LiveVideo.fromJson({
          ...videoJson(),
          'creator_id': accountId,
          'title': 'My own original',
        })
      ], null);
      await pumpHome(tester,
          videos: HomeVideos(trending: () async => own), account: signedIn());
      expect(find.text('My own original'), findsOneWidget);
      expect(find.text('No creators to show yet'), findsOneWidget);
      expect(find.text('Follow'), findsNothing);
    });
  });

  group('navigation', () {
    testWidgets('every control routes to its design destination',
        (tester) async {
      final videos = HomeVideos(trending: () async => twoVideos());
      final fixture = signedIn();
      Future<void> expectRoute(String text, String route,
          [String? entity]) async {
        await pumpHome(tester, videos: videos, account: fixture);
        await tapText(tester, text);
        expect(destinations.last, '$route:${entity ?? ''}', reason: text);
      }

      await expectRoute('Search videos, creators…', '/mobile/M-021');
      await expectRoute('Videos', '/mobile/M-024');
      await expectRoute('Explore', '/mobile/M-019');
      await expectRoute('Creator Studio', '/mobile/M-037');
      await expectRoute('Waterside at dawn', '/mobile/M-025', videoId());
      await expectRoute(
          'City lights, fresh bars', '/mobile/M-025', otherVideoId);
      await expectRoute('Esi Kollie', '/mobile/M-026', heroCreatorId);
      await expectRoute('Profile', '/mobile/M-079');
      await expectRoute('Create', '/mobile/M-037');
    });

    testWidgets('See all links open search and the following feed',
        (tester) async {
      final videos = HomeVideos(trending: () async => twoVideos());
      await pumpHome(tester, videos: videos, account: signedIn());
      final seeAll = find.text('See all');
      expect(seeAll, findsNWidgets(2));
      await tester.tap(seeAll.first);
      await settleAsync(tester);
      expect(destinations.last, '/mobile/M-021:');
      await pumpHome(tester, videos: videos, account: signedIn());
      await tester.ensureVisible(find.text('See all').last);
      await tester.tap(find.text('See all').last);
      await settleAsync(tester);
      expect(destinations.last, '/mobile/M-018:');
    });

    testWidgets('a category chip opens Explore filtered to that category',
        (tester) async {
      final videos = HomeVideos(trending: () async => twoVideos());
      await pumpHome(tester, videos: videos, account: signedIn());
      await tapText(tester, 'Short films');
      expect(find.byType(DiscoveryCatalogScreen), findsWidgets);
      final explore = tester
          .widgetList<DiscoveryCatalogScreen>(
              find.byType(DiscoveryCatalogScreen))
          .last;
      expect(explore.screen, 19);
      expect(explore.initialCategory, 'short_films');
    });
  });

  group('independent states', () {
    testWidgets('signed out: welcome, sign-in prompt, no account requests',
        (tester) async {
      final videos = HomeVideos(trending: () async => twoVideos());
      await pumpHome(tester, videos: videos);
      expect(find.text('Welcome to KoloVibe'), findsOneWidget);
      expect(find.text('Sign in to see who you follow'), findsOneWidget);
      expect(find.text('Waterside at dawn'), findsOneWidget);
      expect(videos.followingCalls, 0);
      await tapText(tester, 'Follow');
      expect(destinations.last, '/mobile/M-004:');
      await pumpHome(tester, videos: videos);
      await tester.tap(find.widgetWithText(InkWell, 'Sign in').first);
      await settleAsync(tester);
      expect(destinations.last, '/mobile/M-004:');
    });

    testWidgets('a rejected session is treated as signed out', (tester) async {
      final videos = HomeVideos(
          trending: () async => twoVideos(),
          following: () async => throw const ApiFailure(401, 'Sign in'));
      final fixture = AccountFixture(
          handler: (_) async => jsonResponse({'error': 'x'}, 401));
      await pumpHome(tester, videos: videos, account: fixture);
      expect(find.text('Sign in to see who you follow'), findsOneWidget);
      expect(find.text('Waterside at dawn'), findsOneWidget);
    });

    testWidgets('empty: every block explains itself without invented content',
        (tester) async {
      await pumpHome(tester, videos: HomeVideos(), account: signedIn());
      expect(find.text('No trending originals yet'), findsOneWidget);
      expect(find.text('No creators to show yet'), findsOneWidget);
      expect(find.text('Nothing here yet'), findsOneWidget);
      expect(find.text('KOLOVIBE ORIGINAL'), findsNothing);
      expect(find.text('TRENDING ORIGINAL'), findsNothing);
      expect(find.text('Follow'), findsNothing);
      expect(find.text('Hipco'), findsOneWidget);
    });

    testWidgets(
        'trending failure does not hide following or chips, retry works',
        (tester) async {
      var fail = true;
      final videos = HomeVideos(
          trending: () async {
            if (fail) throw const ApiFailure(503, 'down');
            return twoVideos();
          },
          following: () async => twoVideos());
      await pumpHome(tester, videos: videos, account: signedIn());
      expect(find.text('Trending is unavailable'), findsOneWidget);
      expect(find.text('Creators are unavailable'), findsOneWidget);
      expect(find.text('FROM CREATORS YOU FOLLOW'), findsWidgets);
      expect(find.text('Hipco'), findsOneWidget);
      fail = false;
      await tapText(tester, 'Try again');
      expect(find.text('Trending is unavailable'), findsNothing);
      expect(find.text('Waterside at dawn'), findsWidgets);
      expect(videos.trendingCalls, 2);
    });

    testWidgets('offline trending failure gives connection guidance',
        (tester) async {
      final videos = HomeVideos(
          trending: () async =>
              throw const ApiFailure(0, 'offline', offline: true));
      await pumpHome(tester, videos: videos, account: signedIn());
      expect(
          find.text('Check your connection, then try again.'), findsOneWidget);
    });

    testWidgets('following failure is isolated from trending', (tester) async {
      final videos = HomeVideos(
          trending: () async => twoVideos(),
          following: () async => throw const ApiFailure(503, 'down'));
      await pumpHome(tester, videos: videos, account: signedIn());
      expect(find.text('Following is unavailable'), findsOneWidget);
      expect(find.text('Waterside at dawn'), findsOneWidget);
      expect(find.text('Esi Kollie'), findsOneWidget);
    });

    testWidgets('creator lookup failure leaves hero and trending intact',
        (tester) async {
      final videos = HomeVideos(trending: () async => twoVideos());
      await pumpHome(tester,
          videos: videos,
          creators: HomeCreators(fail: true),
          account: signedIn());
      expect(find.text('Creators could not be loaded'), findsOneWidget);
      expect(find.text('Waterside at dawn'), findsOneWidget);
      expect(find.text('City lights, fresh bars'), findsOneWidget);
      // Without a creator name the metadata falls back to the real category.
      expect(find.text('Short films'), findsWidgets);
    });

    testWidgets('following feed lists real videos', (tester) async {
      final videos = HomeVideos(
          trending: () async => twoVideos(),
          following: () async => twoVideos());
      await pumpHome(tester, videos: videos, account: signedIn());
      expect(find.text('FROM CREATORS YOU FOLLOW'), findsNWidgets(2));
    });
  });

  group('follow', () {
    testWidgets('optimistic follow is confirmed by the server', (tester) async {
      final videos = HomeVideos(trending: () async => twoVideos());
      final fixture = signedIn();
      await pumpHome(tester, videos: videos, account: fixture);
      await tapText(tester, 'Follow');
      expect(find.widgetWithText(InkWell, 'Following'), findsWidgets);
      final put = fixture.requests.where((r) => r.method == 'PUT');
      expect(put.single.url.path, endsWith('/creators/$heroCreatorId/follow'));
    });

    testWidgets('failed follow rolls back and says so', (tester) async {
      final videos = HomeVideos(trending: () async => twoVideos());
      final fixture = signedIn(onFollow: (_) async => jsonResponse({}, 503));
      await pumpHome(tester, videos: videos, account: fixture);
      await tapText(tester, 'Follow');
      expect(find.text('The follow change could not be confirmed. Try again.'),
          findsOneWidget);
      expect(find.widgetWithText(InkWell, 'Following'), findsNothing);
    });

    testWidgets('an existing follow can be undone', (tester) async {
      final videos = HomeVideos(trending: () async => twoVideos());
      final fixture = signedIn(followed: true);
      await pumpHome(tester, videos: videos, account: fixture);
      expect(find.widgetWithText(InkWell, 'Following'), findsWidgets);
      await tester
          .ensureVisible(find.widgetWithText(InkWell, 'Following').first);
      await tester.tap(find.widgetWithText(InkWell, 'Following').first);
      await settleAsync(tester);
      expect(fixture.requests.where((r) => r.method == 'DELETE'), hasLength(1));
      expect(find.text('Follow'), findsWidgets);
    });
  });

  group('greeting', () {
    Future<void> greet(WidgetTester tester, int hour) async {
      useViewport(tester, AuditViewport.standard);
      await tester.pumpWidget(MaterialApp(
          theme: KoloVibeTheme.light(),
          home: HomeDashboard(
              videos: HomeVideos(),
              catalog: catalog,
              navigate: (_, [__]) {},
              openCategory: (_) {},
              clock: () => DateTime(2026, 11, 19, hour))));
      await settleAsync(tester);
    }

    testWidgets('follows the local time of day', (tester) async {
      await greet(tester, 9);
      expect(find.textContaining('Welcome to KoloVibe'), findsOneWidget);
    });

    testWidgets('morning, afternoon and evening for a signed-in account',
        (tester) async {
      for (final entry in {
        9: 'Good morning, Mark',
        14: 'Good afternoon, Mark',
        20: 'Good evening, Mark'
      }.entries) {
        useViewport(tester, AuditViewport.standard);
        await tester.pumpWidget(MaterialApp(
            theme: KoloVibeTheme.light(),
            home: HomeDashboard(
                videos: HomeVideos(),
                account: AccountFixture().account,
                catalog: catalog,
                navigate: (_, [__]) {},
                openCategory: (_) {},
                clock: () => DateTime(2026, 11, 19, entry.key))));
        await settleAsync(tester);
        expect(find.textContaining(entry.value, findRichText: true),
            findsOneWidget);
        // SIM-01: the morning sun is an icon, never an emoji glyph.
        expect(find.byIcon(Icons.wb_sunny_rounded),
            entry.key == 9 ? findsOneWidget : findsNothing);
        expect(find.textContaining('☀', findRichText: true), findsNothing);
      }
    });
  });

  group('layout', () {
    for (final viewport in [
      AuditViewport.standard,
      AuditViewport.small,
      const AuditViewport('320x568', Size(320, 568), 20, 0),
    ]) {
      for (final scale in [1.0, 1.5, 2.0, 3.0]) {
        testWidgets(
            'no overflow at ${viewport.name}, text ${scale}x, and the whole page scrolls',
            (tester) async {
          final videos = HomeVideos(
              trending: () async => twoVideos(),
              following: () async => twoVideos());
          await pumpHome(tester,
              videos: videos,
              account: signedIn(),
              viewport: viewport,
              textScale: scale);
          if (scale == 1.0) {
            await captureAudit(tester, shot, 'M-017_${viewport.name}',
                design: viewport == AuditViewport.standard ? 17 : null);
          }
          await tester.ensureVisible(find
              .text('Original voices. More approved services as available.'));
          await tester.pumpAndSettle();
          if (scale == 1.0) {
            await captureAudit(tester, shot, 'M-017_${viewport.name}_bottom');
          }
          noException(tester);
        });
      }
    }

    testWidgets('tap targets meet the 44 pt minimum', (tester) async {
      await pumpHome(tester,
          videos: HomeVideos(trending: () async => twoVideos()),
          account: signedIn());
      for (final finder in [
        find.widgetWithText(InkWell, 'Follow'),
        find.widgetWithText(InkWell, 'Hipco'),
        find.widgetWithText(InkWell, 'See all').first,
      ]) {
        await tester.ensureVisible(finder.first);
        final size = tester.getSize(finder.first);
        expect(size.height, greaterThanOrEqualTo(44), reason: '$finder');
        expect(size.width, greaterThanOrEqualTo(44), reason: '$finder');
      }
    });

    testWidgets('keyboard inset never overlaps or breaks the layout',
        (tester) async {
      await pumpHome(tester,
          videos: HomeVideos(trending: () async => twoVideos()),
          account: signedIn(),
          keyboard: 336);
      noException(tester);
    });

    testWidgets('bottom navigation clears the home indicator', (tester) async {
      await pumpHome(tester,
          videos: HomeVideos(trending: () async => twoVideos()),
          account: signedIn());
      final nav = tester.getRect(find.text('Home'));
      expect(nav.bottom, lessThanOrEqualTo(844 - 34));
    });
  });
}

String videoId() => '00000000-0000-4000-8000-000000000003';

void noException(WidgetTester tester) {
  final error = tester.takeException();
  if (error != null) {
    fail(error is FlutterError ? error.toStringDeep() : '$error');
  }
}
