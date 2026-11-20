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
import 'package:kolovibe/features/system/compatibility.dart';
import 'package:kolovibe/features/system/system_ui.dart';
import 'package:kolovibe/features/content/live_content_repository.dart';
import 'package:kolovibe/features/content/live_content_screen.dart';
import 'package:kolovibe/features/content/live_create_original_screen.dart';
import 'package:kolovibe/features/content/live_manage_video_screen.dart';
import 'package:kolovibe/features/creators/live_become_creator_screen.dart';
import 'package:kolovibe/features/creators/live_creator_repository.dart';
import 'package:kolovibe/features/creators/live_creator_screen.dart';
import 'package:kolovibe/features/creators/live_creator_studio_screen.dart';
import 'package:kolovibe/features/creators/live_edit_creator_profile_screen.dart';
import 'package:kolovibe/features/creators/live_own_profile_screen.dart';
import 'package:kolovibe/features/discovery/discovery_catalog_screen.dart';
import 'package:kolovibe/features/discovery/live_video_repository.dart';
import 'package:kolovibe/features/discovery/live_video_screen.dart';
import 'package:kolovibe/features/moderation/live_notice_screen.dart';
import 'package:kolovibe/features/moderation/live_report_screen.dart';
import 'package:kolovibe/features/moderation/live_standing_screen.dart';
import 'package:kolovibe/features/points/live_points_screen.dart';
import 'package:kolovibe/features/points/live_points_repository.dart';
import 'fl_a_support.dart' hide accountId;
import 'fl_b_repositories_test.dart' show videoJson, creatorJson;
import 'support/creator_fakes.dart';
import 'support/points_fakes.dart';
import 'support/report_fakes.dart';
import 'support/standing_fakes.dart';
import 'support/upload_fakes.dart';
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
  final navigator = GlobalKey<NavigatorState>();

  /// Hosts [child] as a pushed route, as in the application, so back arrows
  /// and navigation behave like the real screens.
  Widget host(Widget child) => RepaintBoundary(
      key: shot,
      child: MaterialApp(
          key: UniqueKey(),
          navigatorKey: navigator,
          debugShowCheckedModeBanner: false,
          theme: KoloVibeTheme.light(),
          home: const SizedBox.shrink(),
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
          final screen = build();
          await tester.pumpWidget(host(screen));
          navigator.currentState!.push(MaterialPageRoute<void>(
              settings: RouteSettings(name: '/mobile/$name'),
              builder: (_) => screen));
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

  AccountFixture signedIn() => AccountFixture(handler: (request) async {
        if (request.url.path.endsWith('/follow')) {
          return jsonResponse({
            'creator_id':
                request.url.pathSegments[request.url.pathSegments.length - 2],
            'following': false,
            'follower_count': 2800
          });
        }
        if (request.url.path.endsWith('/me/preferences')) {
          return jsonResponse(
              {'email_notifications': true, 'push_notifications': false});
        }
        if (request.url.path.endsWith('/me/sessions')) {
          return jsonResponse({
            'items': [
              {
                'id': receiptId,
                'created_at': '2026-11-11T12:00:00Z',
                'expires_at': '2026-12-11T12:00:00Z',
                'current': true
              },
              {
                'id': '00000000-0000-4000-8000-000000000008',
                'created_at': '2026-11-09T12:00:00Z',
                'expires_at': '2026-12-09T12:00:00Z',
                'current': false
              }
            ]
          });
        }
        return jsonResponse({});
      });

  final videos = _AuditVideos();
  final creators = _AuditCreators();

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
  audit(
      'M-108',
      108,
      () => CompatibilityScreen(
          policy: CompatibilityPolicy.fromJson({
            'status': 'update_required',
            'minimum_version': '1.0.0',
            'latest_version': '2.0.0',
            'store_url': 'https://store.example.test/kolovibe'
          }),
          device: TestDevice()));
  audit('M-104', 104, () => MediaPermissionScreen(device: TestDevice()));

  // Discovery.
  for (final id in [18, 19, 20, 21, 22, 23, 27]) {
    audit(
        'M-${id.toString().padLeft(3, '0')}',
        id,
        () => DiscoveryCatalogScreen(
            screen: id,
            repository: videos,
            catalog: catalog,
            account: signedIn().account,
            creators: creators,
            creatorId: id == 27 ? creatorId : null,
            initialQuery: id == 22 ? 'Waterside' : null));
  }
  audit(
      'M-025',
      25,
      () =>
          LiveVideoDetailScreen(id: videos.items.first.id, repository: videos));
  audit(
      'M-026',
      26,
      () => LiveCreatorScreen(
          id: creatorId, repository: creators, account: signedIn().account));
  audit(
      'M-031',
      31,
      () => LiveVideoDetailScreen(
          id: videos.items.first.id,
          repository: _AuditVideos(failure: const ApiFailure(404, 'x'))));
  audit(
      'M-035',
      35,
      () => LiveVideoDetailScreen(
          id: videos.items.first.id,
          repository: _AuditVideos(failure: const ApiFailure(403, 'x'))));

  // Creator studio.
  ScriptedOnboarding onboarding({bool eligible = true, String? status}) =>
      ScriptedOnboarding()
        ..eligible = eligible
        ..status = status;
  audit(
      'M-036',
      36,
      () => LiveBecomeCreatorScreen(
          catalog: catalog, onboarding: onboarding(eligible: false)));
  audit(
      'M-037',
      37,
      () => LiveCreatorStudioScreen(
          catalog: catalog,
          onboarding: onboarding(),
          profiles: ScriptedOwnCreator()));
  audit(
      'M-038',
      38,
      () => LiveOwnProfileScreen(
          catalog: catalog,
          profiles: ScriptedOwnCreator(),
          publicCreators: CountingPublicCreators(12)));
  audit(
      'M-039',
      39,
      () => LiveEditCreatorProfileScreen(
          catalog: catalog, profiles: ScriptedOwnCreator()));
  audit(
      'M-040',
      40,
      () => LiveContentScreen(
          route: const ScreenRoute(40),
          catalog: catalog,
          repository: _AuditLibrary()));
  audit(
      'M-041',
      41,
      () => LiveCreateOriginalScreen(
          content: FakeContent(), onboarding: FakeOnboarding()));
  audit(
      'M-053',
      53,
      () =>
          LiveManageVideoScreen(videoId: videoId, repository: _AuditManage()));

  // Lone Stars.
  ScriptedPoints points({List<PointsEntry>? ledger}) => ScriptedPoints()
    ..ledger = ledger ??
        [
          for (var i = 1; i <= 6; i++) ledgerEntry(i, video: videoId),
          ledgerEntry(7, status: 'pending'),
          ledgerEntry(8, status: 'adjustments'),
        ];
  for (final id in [61, 62, 63, 64, 66, 67, 68, 69]) {
    audit(
        'M-${id.toString().padLeft(3, '0')}',
        id,
        () => LivePointsScreen(
            route: ScreenRoute(id),
            catalog: catalog,
            repository: points(ledger: id == 69 ? [] : null),
            videoTitle: (_) async => 'Waterside at dawn'));
  }
  audit(
      'M-065',
      65,
      () => LivePointsScreen(
          route: ScreenRoute(65, entityId: entryId(1)),
          catalog: catalog,
          repository: points(),
          videoTitle: (_) async => 'Waterside at dawn'));

  // Reports, notices and standing.
  // The report journey: each later screen is reached the way a person would.
  Future<void> tapLabel(WidgetTester tester, String label) async {
    if (find.text(label).evaluate().isEmpty) {
      await tester.scrollUntilVisible(find.text(label), 200,
          scrollable: find.byType(Scrollable).first);
    }
    final target = find.text(label).last;
    await tester.ensureVisible(target);
    await tester.pumpAndSettle();
    await tester.tap(target, warnIfMissed: false);
    await settleAsync(tester);
  }

  for (final id in [71, 72, 73, 74, 75]) {
    audit('M-${id.toString().padLeft(3, '0')}', id, () {
      final moderation = ScriptedModeration();
      if (id == 74) moderation.failures.add(offlineReport);
      if (id == 75) moderation.failures.add(alreadyReported);
      return LiveReportScreen(
          route: const ScreenRoute(71, entityId: videoId),
          catalog: catalog,
          videos: ScriptedVideos(),
          moderation: moderation);
    },
        after: id == 71
            ? null
            : (tester) async {
                await tapLabel(tester, 'Rights or ownership concern');
                await tapLabel(tester, 'Continue');
                if (id >= 73) await tapLabel(tester, 'Submit report');
              });
  }
  audit(
      'M-076',
      76,
      () => LiveNoticeScreen(
          route: const ScreenRoute(76, entityId: videoId),
          catalog: catalog,
          repository: ScriptedStanding()
            ..noticeValue = videoNotice(appealable: true)));
  audit(
      'M-077',
      77,
      () => LiveStandingScreen(
          catalog: catalog,
          repository: ScriptedStanding()
            ..standingValue = standingWith([videoId])));
}

class _AuditVideos extends LiveVideoRepository {
  _AuditVideos({this.failure})
      : super(ApiClient('https://api.example.test/api/v1'));
  final Object? failure;
  final items = [
    LiveVideo.fromJson({
      ...videoJson(),
      'creator_id': creatorId,
      'title': 'Waterside at dawn',
      'description': 'A city waking up on the river.',
      'category': 'short_films',
      'like_count': 1240,
    }),
    LiveVideo.fromJson({
      ...videoJson('00000000-0000-4000-8000-000000000004'),
      'creator_id': creatorId,
      'title': 'City lights, fresh bars',
      'category': 'hipco',
      'like_count': 86,
    }),
  ];
  @override
  Future<LiveVideoPage> filteredPage(
          {String? cursor,
          String? creatorId,
          String? query,
          String? category,
          String sort = 'recent'}) async =>
      LiveVideoPage(items, null);
  @override
  Future<LiveVideoPage> followingPage(account, {String? cursor}) async =>
      LiveVideoPage(items, null);
  @override
  Future<LiveVideo> detail(String id) async {
    if (failure != null) throw failure!;
    return items.first;
  }
}

class _AuditCreators extends LiveCreatorRepository {
  _AuditCreators() : super(ApiClient('https://api.example.test/api/v1'));
  LiveCreator get one => LiveCreator.fromJson({
        ...creatorJson(),
        'id': creatorId,
        'handle': 'amakollie',
        'display_name': 'Ama Kollie',
        'bio': 'Finding the cinema in the everyday.',
      });
  @override
  Future<LiveCreator> detail(String id) async => one;
  @override
  Future<({List<LiveCreator> items, String? nextCursor})> search(String query,
          {String? cursor}) async =>
      (items: [one], nextCursor: null);
}

class _AuditLibrary extends LiveContentRepository {
  _AuditLibrary() : super(unusedAccount());
  @override
  Future<OwnedVideoPage> library({String? cursor}) async => OwnedVideoPage([
        OwnedVideo(videoId, creatorId, 'Waterside at dawn', 'A city waking up.',
            'published', DateTime.utc(2026, 11, 11),
            visibility: 'public', category: 'short_films'),
        OwnedVideo('00000000-0000-4000-8000-000000000009', creatorId,
            'Untitled draft', '', 'draft', DateTime.utc(2026, 11, 12)),
      ], null);
}

class _AuditManage extends LiveContentRepository {
  _AuditManage() : super(unusedAccount());
  @override
  Future<OwnedVideo> ownedVideo(String videoId) async => OwnedVideo(
      videoId,
      creatorId,
      'Waterside at dawn',
      'A city waking up.',
      'published',
      DateTime.utc(2026, 11, 11),
      visibility: 'private',
      category: 'short_films',
      revision: 4);
}
