import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/app/app_dependencies.dart';
import 'package:kolovibe/app/app_session.dart';
import 'package:kolovibe/app/screen_route.dart';
import 'package:kolovibe/features/shell/mobile_screen.dart';
import 'package:kolovibe/shared/widgets/kolo_media.dart'
    show posterProviderOverride;
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
import 'package:kolovibe/features/content/live_upload_controller.dart';
import 'package:kolovibe/features/creators/live_become_creator_screen.dart';
import 'package:kolovibe/features/creators/live_analytics_repository.dart';
import 'package:kolovibe/features/creators/live_analytics_screen.dart';
import 'package:kolovibe/features/creators/live_creator_repository.dart';
import 'package:kolovibe/features/creators/live_creator_screen.dart';
import 'package:kolovibe/features/creators/live_creator_studio_screen.dart';
import 'package:kolovibe/features/creators/live_edit_creator_profile_screen.dart';
import 'package:kolovibe/features/creators/live_own_profile_screen.dart';
import 'package:kolovibe/features/discovery/discovery_catalog_screen.dart';
import 'package:kolovibe/features/discovery/live_video_repository.dart';
import 'package:kolovibe/features/discovery/search_history.dart';
import 'package:kolovibe/features/discovery/live_video_screen.dart';
import 'package:kolovibe/features/discovery/vertical_video_feed.dart';
import 'package:kolovibe/features/engagement/live_video_engagement_repository.dart';
import 'package:kolovibe/features/account/live_account_repository.dart';
import 'package:kolovibe/features/moderation/live_appeal_screen.dart';
import 'package:kolovibe/features/moderation/live_moderation_repository.dart';
import 'package:kolovibe/features/moderation/live_notice_screen.dart';
import 'package:kolovibe/features/moderation/live_report_screen.dart';
import 'package:kolovibe/features/moderation/live_standing_screen.dart';
import 'package:kolovibe/features/points/live_points_screen.dart';
import 'package:kolovibe/features/points/live_points_repository.dart';
import 'fl_a_support.dart' hide accountId;
import 'fl_b_repositories_test.dart' show videoJson, creatorJson, playbackJson;
import 'fl_b_widgets_test.dart' show FakePlayer;
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
    // Local design artwork, found by file-name prefix so no long hash literals
    // appear in the test.
    const prefixes = ['cf4e', 'cf42', 'bc60', '7946', '87df'];
    final files = Directory('assets/images')
        .listSync()
        .map((e) => e.path.split('/').last)
        .where((n) => n.endsWith('.png'))
        .toList();
    final artwork = [
      for (final prefix in prefixes)
        files.firstWhere((n) => n.startsWith(prefix))
    ];
    posterProviderOverride = (url) => AssetImage(
        'assets/images/${artwork[int.parse(url.pathSegments.last) % artwork.length]}');
  });
  tearDownAll(() => posterProviderOverride = null);

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
      {Future<void> Function(WidgetTester)? after,
      Future<void> Function(WidgetTester)? finish,
      bool bounded = false}) {
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
          bounded ? await settleBounded(tester) : await settleAsync(tester);
          if (after != null) await after(tester);
          final error = tester.takeException();
          if (error != null) {
            fail(error is FlutterError ? error.toStringDeep() : '$error');
          }
          if (scale == 1.0) {
            await captureAudit(tester, shot, '${name}_${viewport.name}',
                design: viewport == AuditViewport.standard ? number : null);
          }
          if (finish != null) await finish(tester);
        });
      }
    }
  }

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

  // M-001 to M-003 are the declarative introduction recipes. The splash is
  // captured before its 900 ms hand-off to the welcome screen.
  for (final id in [1, 2, 3]) {
    audit(
        'M-${id.toString().padLeft(3, '0')}',
        id,
        () => MobileScreen(
            route: ScreenRoute(id),
            catalog: catalog,
            dependencies: const AppDependencies.unavailable(),
            session: AppSession()),
        bounded: id == 1);
  }
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
  // Account states: each is reached the way a person would reach it.
  audit(
      'M-006-verifying',
      6,
      () => LiveAccountFlowScreen(
          screen: 6,
          account: AccountFixture(handler: (_) async {
            await Future<void>.delayed(const Duration(milliseconds: 300));
            return jsonResponse({}, 400);
          }).account,
          catalog: catalog,
          initialEmail: 'ama@example.com'), after: (tester) async {
    await tester.enterText(
        find.byType(TextField).first, '482619');
    final verify = find.text('Verify email');
    if (verify.evaluate().isEmpty) {
      await tester.scrollUntilVisible(verify, 200,
          scrollable: find.byType(Scrollable).first);
    }
    await tester.pump();
    await tester.tap(verify);
    await tester.pump(const Duration(milliseconds: 100));
  }, finish: (tester) async {
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pumpWidget(const SizedBox());
  });
  audit(
      'M-007-sent',
      7,
      () => LiveAccountFlowScreen(
          screen: 7,
          account: signedIn().account,
          catalog: catalog,
          initialEmail: 'ama@example.com',
          completed: true));
  audit(
      'M-007-unavailable',
      7,
      () => LiveAccountFlowScreen(
          screen: 7,
          account: AccountFixture(
                  handler: (_) async => jsonResponse({'detail': 'slow'}, 429))
              .account,
          catalog: catalog,
          initialEmail: 'ama@example.com'), after: (tester) async {
    await tapLabel(tester, 'Request a new code');
  });
  audit(
      'M-009-sent',
      9,
      () => LiveAccountFlowScreen(
          screen: 9,
          account: signedIn().account,
          catalog: catalog,
          initialEmail: 'ama@example.com'), after: (tester) async {
    await tapLabel(tester, 'Send reset instructions');
  });
  audit(
      'M-011-done',
      11,
      () => LiveAccountFlowScreen(
          screen: 11,
          account: signedIn().account,
          catalog: catalog,
          completed: true));
  audit(
      'M-012-existing',
      12,
      () => LiveAccountFlowScreen(
          screen: 12,
          account: signedIn().account,
          catalog: catalog,
          initialEmail: 'ama@example.com'));
  // M-105 unsaved-changes guard, M-106 destructive confirmation and M-107
  // success notification, each reached through a real screen.
  audit(
      'M-105',
      105,
      () => LiveAccountFlowScreen(
          screen: 80,
          account: signedIn().account,
          catalog: catalog), after: (tester) async {
    await tester.enterText(find.byType(TextFormField).first, 'Mark Edited');
    await tester.pump();
    unawaited(navigator.currentState!.maybePop());
    await settleBounded(tester);
  });
  audit(
      'M-106', 106, () => AccountSessionsScreen(repository: signedIn().account),
      after: (tester) async {
    await tester.tap(find.text('End session').first);
    await settleBounded(tester);
  });
  audit(
      'M-107',
      107,
      () => AccountSessionsScreen(
              repository: AccountFixture(handler: (request) async {
            if (request.method == 'DELETE') return jsonResponse({}, 204);
            return signedIn().handler!(request);
          }).account),
      after: (tester) async {
        await tester.tap(find.text('End session').first);
        await settleBounded(tester);
        await tester.tap(find.widgetWithText(FilledButton, 'End session'));
        await settleBounded(tester);
      },
      finish: (tester) async => tester.pump(const Duration(seconds: 5)));
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
  for (final id in [84, 85, 86, 91, 92]) {
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
  // M-093 and M-094: the populated receipts the service returns.
  for (final id in [93, 94]) {
    audit('M-0$id', id, () {
      final fixture = signedIn();
      return LiveSettingsScreen(
          route: ScreenRoute(id),
          catalog: catalog,
          repository: LiveSettingsRepository(fixture.account),
          account: fixture.account,
          device: TestDevice(),
          receipt: PrivacyReceipt(receiptId, id == 93 ? 'deletion' : 'access',
              'received', DateTime.utc(2026, 11, 20, 9, 30)));
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
  // M-096: the same loading placeholder once a request passes its 3 s threshold.
  audit(
      'M-096', 96, () => const Scaffold(body: SafeArea(child: SystemLoading())),
      bounded: true, after: (tester) async {
    await tester.pump(const Duration(seconds: 4));
  });
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
  for (final id in [19, 20, 21, 22, 27]) {
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
  // D-5: M-021 with a signed-in account's device-local recent searches. The account only reports an
  // id (no network, no timers), so the capture cannot hang on a request.
  audit(
      'M-021-recent',
      21,
      () => DiscoveryCatalogScreen(
          screen: 21, repository: videos, catalog: catalog),
      after: (tester) async {
    final history = SearchHistory(MemorySearchHistoryStore());
    final account = _SignedInAccount(signedIn().account);
    for (final term in ['river songs', 'Monrovia street food', 'hipco nights']) {
      await history.add(account.signedInAccountId, term);
    }
    navigator.currentState!.push(MaterialPageRoute<void>(
        settings: const RouteSettings(name: '/mobile/M-021'),
        builder: (_) => DiscoveryCatalogScreen(
            screen: 21,
            repository: videos,
            catalog: catalog,
            account: account,
            history: history,
            creators: creators)));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    await tester.pump(const Duration(milliseconds: 50));
  });
  // M-023 is the category sheet opened from the search results, as designed.
  audit(
      'M-023',
      23,
      () => DiscoveryCatalogScreen(
          screen: 22,
          repository: videos,
          catalog: catalog,
          account: signedIn().account,
          creators: creators,
          initialQuery: 'Waterside'), after: (tester) async {
    await tester.tap(find.byTooltip('Filters'));
    await settleAsync(tester);
  });
  audit(
      'M-023-page',
      23,
      () => DiscoveryCatalogScreen(
          screen: 23,
          repository: videos,
          catalog: catalog,
          account: signedIn().account,
          creators: creators));
  audit(
      'M-020-fresh',
      20,
      () => DiscoveryCatalogScreen(
          screen: 20,
          repository: videos,
          catalog: catalog,
          account: signedIn().account,
          creators: creators), after: (tester) async {
    await tester.tap(find.text('Fresh picks'));
    await settleAsync(tester);
  });
  audit(
      'M-022-creators',
      22,
      () => DiscoveryCatalogScreen(
          screen: 22,
          repository: videos,
          catalog: catalog,
          account: signedIn().account,
          creators: creators,
          initialQuery: 'Waterside'), after: (tester) async {
    await tester.tap(find.text('Creators').first);
    await settleAsync(tester);
  });
  // The vertical feeds, rendered with an in-memory player (no platform view).
  for (final following in [false, true]) {
    audit(
        following ? 'M-018' : 'M-024',
        following ? 18 : 24,
        () => VerticalVideoFeed(
            repository: videos,
            device: TestDevice(),
            following: following,
            catalog: catalog,
            account: following ? signedIn().account : null,
            creators: creators,
            playerFactory: (_) => FakePlayer()));
  }
  // Player states, reached through the real player controller and fixtures.
  final firstId = videos.items.first.id;
  AccountFixture likesAndShares() => AccountFixture(handler: (request) async {
        if (request.url.path.endsWith('/shares')) {
          return jsonResponse({
            'video_id': firstId,
            'share_url': 'https://web.example.test/videos/$firstId'
          });
        }
        if (request.url.path.endsWith('/watch-sessions')) {
          return jsonResponse({
            'session_id': receiptId,
            'session_expires_at': proofData['expires_at'],
            'playback_url': playbackJson()['playback_url'],
            'playback_expires_at': playbackJson()['expires_at']
          });
        }
        if (request.url.path.endsWith('/like')) {
          final liked = request.method == 'PUT';
          return jsonResponse({
            'video_id': firstId,
            'liked': liked,
            'like_count': 1240 + (liked ? 1 : 0)
          });
        }
        return jsonResponse({});
      });
  Widget playerScreen({FakePlayer? player, AccountFixture? fixture}) =>
      VerticalVideoFeed(
          repository: videos,
          device: TestDevice(),
          catalog: catalog,
          account: fixture?.account,
          engagement: fixture == null
              ? null
              : LiveVideoEngagementRepository(fixture.account),
          creators: creators,
          playerFactory: (_) => player ?? FakePlayer());
  audit('M-070', 70, () => playerScreen(fixture: likesAndShares()),
      after: (tester) async {
    await tester.tap(find.byTooltip('More'));
    await settleBounded(tester);
  });
  audit('M-029', 29, () => playerScreen(fixture: likesAndShares()),
      after: (tester) async {
    await tester.tap(find.byTooltip('Like'));
    await settleBounded(tester);
  });
  audit('M-030', 30, () => playerScreen(fixture: likesAndShares()),
      after: (tester) async {
    await tester.tap(find.byTooltip('Share'));
    await settleBounded(tester);
  });
  final stalled = <FakePlayer>[];
  FakePlayer pendingPlayer() {
    final player = FakePlayer()..pending = Completer<void>();
    stalled.add(player);
    return player;
  }

  Future<void> release(WidgetTester tester) async {
    for (final player in stalled) {
      if (!(player.pending?.isCompleted ?? true)) player.pending!.complete();
    }
    stalled.clear();
    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(seconds: 6));
  }

  audit('M-032', 32, () => playerScreen(player: pendingPlayer()),
      bounded: true, finish: release);
  audit('M-034', 34, () => playerScreen(player: pendingPlayer()),
      bounded: true,
      after: (tester) async => tester.pump(const Duration(seconds: 6)),
      finish: release);
  audit('M-033', 33, () => playerScreen(player: FakePlayer()..fail = true),
      after: (tester) async => settleBounded(tester));
  audit(
      'M-025',
      25,
      () => LiveVideoDetailScreen(
          id: videos.items.first.id, repository: videos, creators: creators));
  audit(
      'M-026',
      26,
      () => LiveCreatorScreen(
          id: creatorId, repository: creators, account: signedIn().account));
  // M-028: the creator page after a confirmed follow (PUT), with the designed
  // "You're connected" note and the confirmation toast.
  audit(
      'M-028',
      28,
      () => LiveCreatorScreen(
          id: creatorId,
          repository: creators,
          account: AccountFixture(handler: (request) async {
            if (request.url.path.endsWith('/follow')) {
              return jsonResponse({
                'creator_id': creatorId,
                'following': request.method == 'PUT',
                'follower_count': request.method == 'PUT' ? 2801 : 2800
              });
            }
            return jsonResponse({});
          }).account),
      after: (tester) async {
        await tapLabel(tester, 'Follow Ama');
        await tester.pump(const Duration(milliseconds: 300));
      },
      finish: (tester) async => tester.pump(const Duration(seconds: 5)));
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
  // The upload journey: each step is reached through the real controller.
  for (final step in [42, 43, 44]) {
    audit(
        'M-0$step',
        step,
        () => LiveCreateOriginalScreen(
            content: FakeContent(),
            onboarding: FakeOnboarding(),
            pickVideo: () async => mp4(size: 2048)),
        after: step == 42
            ? null
            : (tester) async {
                await tester.tap(find.text('Select a video'));
                await settleAsync(tester);
              });
  }
  // The upload journey after "Create and upload": each state is reached
  // through the real controller with a scripted content service.
  Future<void> uploadThrough(WidgetTester tester) async {
    await tapLabel(tester, 'Select a video');
    // File selection replaces a short list with the details form. Start at its
    // top; the previous offset may otherwise put the first label above view.
    tester
        .state<ScrollableState>(find.byType(Scrollable).first)
        .position
        .jumpTo(0);
    await tester.pump();
    Future<void> type(String label, String value) async {
      final field = find.byWidgetPredicate((widget) =>
          widget is TextField && widget.decoration?.labelText == label);
      if (field.evaluate().isEmpty) {
        await tester.scrollUntilVisible(field, 200,
            scrollable: find.byType(Scrollable).first);
      }
      await tester.ensureVisible(field);
      await tester.pump();
      await tester.enterText(field, value);
      await tester.pump();
    }

    await type('Title · Required', 'Walls that speak');
    await type('Description', 'An afternoon with the artists.');
    final dropdown = find.byType(DropdownButtonFormField<String>);
    if (dropdown.evaluate().isEmpty) {
      await tester.scrollUntilVisible(dropdown, 200,
          scrollable: find.byType(Scrollable).first);
    }
    tester
        .widget<DropdownButtonFormField<String>>(dropdown)
        .onChanged!('culture');
    await tester.pump();
    await type('Hashtags · Optional', '#Monrovia #StreetArt');
    final consent = find.byType(CheckboxListTile);
    if (consent.evaluate().isEmpty) {
      await tester.scrollUntilVisible(consent, 200,
          scrollable: find.byType(Scrollable).first);
    }
    await tester.ensureVisible(consent);
    await tester.pump();
    await tester.tap(consent);
    await tester.pump();
    final submit = find.text('Create and upload');
    await tester.ensureVisible(submit);
    await tester.pump();
    await tester.tap(submit);
    for (var i = 0; i < 6; i++) {
      await tester.runAsync(
          () => Future<void>.delayed(const Duration(milliseconds: 5)));
      await tester.pump(const Duration(milliseconds: 50));
    }
  }

  void uploadState(String name, int number, void Function(FakeContent) setup,
      {Completer<void>? gate}) {
    audit(
        name,
        number,
        () {
          final content = FakeContent();
          setup(content);
          if (gate != null) content.transferGate = gate;
          final onboarding = FakeOnboarding();
          return LiveCreateOriginalScreen(
              catalog: catalog,
              content: content,
              onboarding: onboarding,
              // Polling never fires in a capture: a delay that does not
              // complete leaves no timer behind.
              controller: LiveUploadController(content, onboarding,
                  delay: (_) => Completer<void>().future),
              pickVideo: () async => mp4(size: 2048));
        },
        bounded: true,
        after: uploadThrough,
        finish: (tester) async {
          if (gate != null && !gate.isCompleted) gate.complete();
          await tester.pumpWidget(const SizedBox());
          await tester.pump(const Duration(seconds: 1));
        });
  }

  uploadState('M-046', 46, (_) {}, gate: Completer<void>());
  uploadState('M-047', 47,
      (c) => c.transferError = const ApiFailure(0, 'x', offline: true));
  uploadState(
      'M-048',
      48,
      (c) => c.completion =
          FakeContent.status('failed', reason: 'upload_missing'));
  uploadState('M-049', 49, (_) {});
  uploadState('M-050', 50, (c) => c.completion = FakeContent.status('review'));
  uploadState(
      'M-051', 51, (c) => c.completion = FakeContent.status('published'));
  uploadState(
      'M-052', 52, (c) => c.completion = FakeContent.status('rejected'));

  // Analytics (M-058 to M-060) against scripted gateway responses.
  Map<String, Object?> analyticsJson(String range, {bool empty = false}) {
    final days = range == '7d' ? 7 : 28;
    return {
      'total_videos': empty ? 0 : 12,
      'videos_by_state': {},
      'range': range,
      'qualified_plays': empty ? 0 : 18200,
      'watch_time_seconds': empty ? 0 : 2311200,
      'likes': empty ? 0 : 1826,
      'new_followers': empty ? 0 : 184,
      'shares': empty ? 0 : 412,
      'daily': [
        for (var i = 0; i < days; i++)
          {
            'date': DateTime.utc(2026, 10, 22 + i - (days - 7))
                .toIso8601String()
                .substring(0, 10),
            'qualified_plays': empty ? 0 : 1200 + (i * 937) % 2400,
            'likes': empty ? 0 : 100 + i * 7
          }
      ],
      'top_videos': empty
          ? []
          : [
              {
                'video_id': videoId,
                'title': 'Waterside at dawn',
                'qualified_plays': 12400
              }
            ],
    };
  }

  LiveAnalyticsRepository analyticsFixture({int? status, bool empty = false}) {
    final fixture = AccountFixture(handler: (request) async {
      if (status != null) return jsonResponse({'detail': 'x'}, status);
      if (request.url.path.endsWith('/analytics') &&
          request.url.path.contains('/videos/')) {
        final range = request.url.queryParameters['range']!;
        return jsonResponse({
          'video_id': videoId,
          'state': 'published',
          'current_likes': 1248,
          'qualified_viewers': 9800,
          'range': range,
          'qualified_plays': empty ? 0 : 12400,
          'watch_time_seconds': empty ? 0 : 1576800,
          'likes': empty ? 0 : 1248,
          'shares': empty ? 0 : 216,
          'average_watch_seconds': empty ? 0 : 127
        });
      }
      if (request.url.path.endsWith('/analytics')) {
        return jsonResponse(
            analyticsJson(request.url.queryParameters['range']!, empty: empty));
      }
      return jsonResponse({});
    });
    return LiveAnalyticsRepository(fixture.account);
  }

  audit(
      'M-058',
      58,
      () =>
          LiveAnalyticsScreen(catalog: catalog, analytics: analyticsFixture()));
  audit(
      'M-059',
      59,
      () => LiveAnalyticsScreen(
          catalog: catalog,
          analytics: analyticsFixture(),
          content: _AuditManage(),
          videoId: videoId));
  audit(
      'M-060',
      60,
      () => LiveAnalyticsScreen(
          catalog: catalog, analytics: analyticsFixture(empty: true)));
  audit(
      'M-060-unavailable',
      60,
      () => LiveAnalyticsScreen(
          catalog: catalog, analytics: analyticsFixture(status: 503)));
  audit(
      'M-037-analytics',
      37,
      () => LiveCreatorStudioScreen(
          catalog: catalog,
          onboarding: onboarding(),
          profiles: ScriptedOwnCreator(),
          analytics: analyticsFixture()));
  audit(
      'M-053',
      53,
      () => LiveManageVideoScreen(
          videoId: videoId,
          catalog: catalog,
          repository: _AuditManage(visibility: 'public'),
          analytics: analyticsFixture()));
  // M-054 edit details, M-055 unpublish and M-056 delete confirmations.
  audit(
      'M-054',
      54,
      () => LiveManageVideoScreen(
          videoId: videoId,
          catalog: catalog,
          repository: _AuditManage(visibility: 'public')),
      after: (tester) async => tapLabel(tester, 'Edit details'));
  audit(
      'M-055',
      55,
      () => LiveManageVideoScreen(
          videoId: videoId,
          catalog: catalog,
          repository: _AuditManage(visibility: 'public')),
      after: (tester) async => tapLabel(tester, 'Unpublish'));
  audit(
      'M-056',
      56,
      () => LiveManageVideoScreen(
          videoId: videoId,
          catalog: catalog,
          repository: _AuditManage(visibility: 'public')),
      after: (tester) async => tapLabel(tester, 'Delete video'));

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
  // M-078: the designed "availability not confirmed" state, then the proposed
  // eligible state (no Figma export exists for it; 0 selects no export).
  for (final eligible in [false, true]) {
    audit(
        eligible ? 'M-078-eligible' : 'M-078',
        eligible ? 0 : 78,
        () => LiveAppealScreen(
            route: const ScreenRoute(78, entityId: videoId),
            catalog: catalog,
            standing: ScriptedStanding()
              ..noticeValue = videoNotice(appealable: eligible),
            moderation: LiveModerationRepository(signedIn().account)));
  }
  // M-078 eligible states (D-7). The Figma frames for these are a revision pending owner review.
  LiveModerationRepository appealGateway(
      {int status = 201, Completer<void>? hold}) {
    final fixture = AccountFixture(handler: (request) async {
      if (request.url.path.endsWith('/appeals')) {
        if (hold != null) await hold.future;
        return jsonResponse(
            status == 201
                ? {
                    'id': '00000000-0000-4000-8000-000000000a01',
                    'video_id': videoId,
                    'status': 'open',
                    'created_at': '2026-11-20T12:04:00Z',
                  }
                : {'detail': 'unavailable'},
            status);
      }
      return jsonResponse({});
    });
    return LiveModerationRepository(fixture.account);
  }

  const statement =
      'The recording is my own work. I wrote and performed the song, and the sample in the intro is licensed. I can share the licence if you need it.';
  Future<void> writeAndSend(WidgetTester tester, String text) async {
    await tester.enterText(find.byType(TextFormField), text);
    final submit = find.text('Send review request');
    await tester.ensureVisible(submit);
    await tester.pump();
    await tester.tap(submit);
  }

  for (final (suffix, gateway, text, hold) in [
    ('-validation', 201, 'Not fair', false),
    ('-sending', 201, statement, true),
    ('-failure', 503, statement, false),
    ('-receipt', 201, statement, false),
  ]) {
    // Each viewport/text-scale case needs its own held request. Reusing a
    // completed gate across tests leaves the HTTP timeout from a later request
    // active at test teardown.
    late Completer<void> holder;
    audit(
        'M-078-eligible$suffix',
        0,
        () {
          holder = Completer<void>();
          return LiveAppealScreen(
              route: const ScreenRoute(78, entityId: videoId),
              catalog: catalog,
              standing: ScriptedStanding()
                ..noticeValue = videoNotice(appealable: true),
              moderation: appealGateway(
                  status: gateway, hold: hold ? holder : null));
        },
        after: (tester) async {
      await writeAndSend(tester, text);
      if (hold) {
        await tester.runAsync(
            () => Future<void>.delayed(const Duration(milliseconds: 150)));
        await tester.pump();
        expect(find.text('Sending…'), findsOneWidget);
      } else {
        await settleAsync(tester);
      }
    }, finish: (tester) async {
      if (!holder.isCompleted) holder.complete();
      if (hold) await settleAsync(tester);
      await tester.pumpWidget(const SizedBox());
      await tester.pump();
    });
  }
  audit(
      'M-057',
      57,
      () => LiveNoticeScreen(
          route: const ScreenRoute(57, entityId: videoId),
          catalog: catalog,
          repository: ScriptedStanding()
            ..noticeValue = videoNotice(appealable: false)));
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
  // Fixture data for the audit only; posters are local design artwork served
  // through `posterProviderOverride`, never through the network.
  final items = [
    for (final (index, title, category, likes, seconds) in [
      (0, 'Waterside at dawn', 'short_films', 1240, 258),
      (1, 'City lights, fresh bars', 'hipco', 86, 118),
      (2, 'Walls that speak', 'culture', 826, 166),
      (3, 'The rhythm of home', 'documentaries', 412, 192),
      (4, 'Inside the session', 'afrobeats', 260, 118),
    ])
      LiveVideo.fromJson({
        ...videoJson(index == 0
            ? '00000000-0000-4000-8000-000000000003'
            : '00000000-0000-4000-8000-00000000001$index'),
        'creator_id': creatorId,
        'title': title,
        'description': 'A city waking up on the river.',
        'category': category,
        'like_count': likes,
        'play_count': const [18400, 2310, 845, 120, 0][index],
        'duration_seconds': seconds,
        'poster_url': 'https://media.example.test/poster/$index',
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

  @override
  Future<PlaybackGrant> playback(String id,
          {LiveAccountRepository? account}) async =>
      PlaybackGrant.fromJson({
        'playback_url': 'https://media.example.test/signed/video',
        'expires_at': DateTime.now()
            .toUtc()
            .add(const Duration(minutes: 5))
            .toIso8601String()
      }, tracked: false);
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
  Future<OwnedVideoPage> library(
          {String? cursor, String state = 'all'}) async =>
      OwnedVideoPage([
        OwnedVideo(videoId, creatorId, 'Waterside at dawn', 'A city waking up.',
            'published', DateTime.utc(2026, 11, 11),
            visibility: 'public', category: 'short_films'),
        OwnedVideo('00000000-0000-4000-8000-000000000009', creatorId,
            'Untitled draft', '', 'draft', DateTime.utc(2026, 11, 12)),
      ], null);
}

class _AuditManage extends LiveContentRepository {
  _AuditManage({this.visibility = 'private'}) : super(unusedAccount());
  final String visibility;
  @override
  Future<OwnedVideo> ownedVideo(String videoId) async => OwnedVideo(
      videoId,
      creatorId,
      'Waterside at dawn',
      'A city waking up.',
      'published',
      DateTime.utc(2026, 11, 11),
      visibility: visibility,
      category: 'short_films',
      durationMs: 258000,
      posterUrl: 'https://media.example.test/poster/0',
      revision: 4);
}

/// A signed-in account for the audit only: it reports an id and does nothing else.
class _SignedInAccount extends LiveAccountRepository {
  _SignedInAccount(LiveAccountRepository base) : super(base.api, base.store);
  @override
  String? get signedInAccountId => '00000000-0000-4000-8000-000000000001';
}
