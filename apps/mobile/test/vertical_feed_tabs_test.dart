import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/core/theme/kolovibe_theme.dart';
import 'package:kolovibe/features/account/live_account_repository.dart';
import 'package:kolovibe/features/discovery/live_video_repository.dart';
import 'package:kolovibe/features/discovery/vertical_video_feed.dart';
import 'package:kolovibe/features/engagement/live_video_engagement_repository.dart'
    show PlaybackGrant;
import 'fl_a_support.dart' hide accountId;
import 'fl_b_repositories_test.dart' show videoJson;
import 'fl_b_widgets_test.dart' show FakePlayer;
import 'support/audit_harness.dart';

class _Feeds extends LiveVideoRepository {
  _Feeds({this.followingFailure})
      : super(ApiClient('https://api.example.test/api/v1'));
  final Object? followingFailure;
  int publicReads = 0, followingReads = 0;
  final video = LiveVideo.fromJson({...videoJson(), 'title': 'Waterside'});
  @override
  Future<LiveVideoPage> page(
      {String? cursor, String? creatorId, String? query}) async {
    publicReads++;
    return LiveVideoPage([video], null);
  }

  @override
  Future<LiveVideoPage> followingPage(LiveAccountRepository account,
      {String? cursor}) async {
    followingReads++;
    if (followingFailure != null) throw followingFailure!;
    return LiveVideoPage([video], null);
  }

  @override
  Future<LiveVideo> detail(String id) async => video;
  @override
  Future<PlaybackGrant> playback(String id,
          {LiveAccountRepository? account}) async =>
      PlaybackGrant.fromJson({
        'playback_url': 'https://media.example.test/v',
        'expires_at': DateTime.now()
            .toUtc()
            .add(const Duration(minutes: 5))
            .toIso8601String()
      }, tracked: false);
}

void main() {
  late DesignCatalog catalog;
  setUpAll(() async {
    catalog = await DesignCatalog.load();
    await loadBrandFonts();
  });
  final pushed = <RouteSettings>[];

  Future<_Feeds> pump(WidgetTester tester,
      {bool following = true,
      Object? failure,
      AuditViewport viewport = AuditViewport.standard}) async {
    useViewport(tester, viewport);
    pushed.clear();
    final repo = _Feeds(followingFailure: failure);
    await tester.pumpWidget(MaterialApp(
        key: UniqueKey(),
        theme: KoloVibeTheme.light(),
        onGenerateRoute: (settings) {
          pushed.add(settings);
          return MaterialPageRoute<void>(
              settings: settings,
              builder: (_) => const Scaffold(body: Text('next')));
        },
        home: VerticalVideoFeed(
            repository: repo,
            device: TestDevice(),
            following: following,
            account: following ? AccountFixture().account : null,
            catalog: catalog,
            playerFactory: (_) => FakePlayer())));
    await settleBounded(tester);
    return repo;
  }

  testWidgets('Following reads the followed feed and has no stock app bar',
      (tester) async {
    final repo = await pump(tester);
    expect(repo.followingReads, 1);
    expect(repo.publicReads, 0);
    expect(find.text('Original'), findsNothing);
    expect(find.text('Following'), findsOneWidget);
    expect(find.text('For You'), findsOneWidget);
    expect(find.text('Videos'), findsOneWidget, reason: 'bottom navigation');
    expect(tester.takeException(), isNull);
  });

  testWidgets('For You reads the public feed and Following tab switches',
      (tester) async {
    final repo = await pump(tester, following: false);
    expect(repo.publicReads, 1);
    expect(repo.followingReads, 0);
    await tester.tap(find.text('Following'));
    await settleBounded(tester);
    expect(pushed.last.name, '/mobile/M-018');
  });

  testWidgets('tabs and search route to their screens', (tester) async {
    await pump(tester);
    await tester.tap(find.text('For You'));
    await settleBounded(tester);
    expect(pushed.last.name, '/mobile/M-024');
    await pump(tester);
    await tester.tap(find.byTooltip('Search'));
    await settleBounded(tester);
    expect(pushed.last.name, '/mobile/M-021');
  });

  testWidgets('a signed-out Following feed asks to sign in', (tester) async {
    await pump(tester, failure: const ApiFailure(401, 'Sign in'));
    expect(find.text('Session expired'), findsOneWidget);
    await tester.tap(find.text('Sign in'));
    await settleBounded(tester);
    expect(pushed.last.name, '/mobile/M-004');
  });

  testWidgets('an empty Following feed explains itself', (tester) async {
    useViewport(tester, AuditViewport.small);
    await tester.pumpWidget(MaterialApp(
        theme: KoloVibeTheme.light(),
        home: VerticalVideoFeed(
            repository: _EmptyFeed(),
            device: TestDevice(),
            following: true,
            account: AccountFixture().account)));
    await settleBounded(tester);
    expect(find.text('Follow creators to see their originals here.'),
        findsOneWidget);
  });
}

class _EmptyFeed extends _Feeds {
  @override
  Future<LiveVideoPage> followingPage(LiveAccountRepository account,
          {String? cursor}) async =>
      const LiveVideoPage([], null);
}
