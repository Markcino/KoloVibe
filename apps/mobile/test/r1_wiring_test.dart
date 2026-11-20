import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kolovibe/app/app_dependencies.dart';
import 'package:kolovibe/app/kolovibe_app.dart';
import 'package:kolovibe/app/screen_route.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'fl_a_support.dart';
import 'support/audit_harness.dart';

/// Drives the real application (real routes, real repositories, real HTTP
/// client) against a recording fake gateway and asserts that each R1 action
/// sends the intended request. This proves wiring, not the staging service or
/// a device.
const heroId = '00000000-0000-4000-8000-0000000000b1';
const secondId = '00000000-0000-4000-8000-0000000000b2';
const creatorOne = '00000000-0000-4000-8000-0000000000c1';
const creatorTwo = '00000000-0000-4000-8000-0000000000c2';
const noticeVideo = '00000000-0000-4000-8000-0000000000b3';
const sessionId = '00000000-0000-4000-8000-0000000000d1';

Map<String, Object?> video(String id, String creator, String title,
        {String category = 'short_films', int likes = 12}) =>
    {
      'id': id,
      'creator_id': creator,
      'title': title,
      'description': 'A story',
      'state': 'published',
      'visibility': 'public',
      'category': category,
      'tags': <String>[],
      'published_at': '2026-11-11T12:00:00Z',
      'like_count': likes,
      'poster_url': 'https://media.example.test/poster'
    };

class Gateway {
  final calls = <String>[];
  final bodies = <String, Object?>{};
  final headers = <String, Map<String, String>>{};
  bool liked = false, followed = false, appealable = true;
  int meReads = 0, refreshes = 0;

  http.Response ok(Object? body, [int status = 200]) =>
      http.Response(jsonEncode(body), status,
          headers: {'content-type': 'application/json'});

  Future<http.Response> handle(http.Request request) async {
    final path = request.url.path.replaceFirst('/api/v1', '');
    final key = '${request.method} $path';
    calls.add(key);
    headers[key] = request.headers;
    if (request.body.isNotEmpty) bodies[key] = jsonDecode(request.body);
    if (key == 'POST /auth/refresh') {
      refreshes++;
      return ok({'access_token': 'access', 'refresh_token': 'rotated'});
    }
    if (key == 'GET /me') {
      meReads++;
      return ok({
        'id': accountId,
        'email': 'tester@example.test',
        'display_name': 'Kofi Mensah',
        'roles': ['user', 'creator']
      });
    }
    if (key == 'GET /videos') {
      return ok({
        'items': [
          video(heroId, creatorOne, 'Waterside at dawn'),
          video(secondId, creatorTwo, 'City lights', category: 'hipco'),
        ],
        'next_cursor': null
      });
    }
    if (key == 'GET /videos/following') {
      return ok({
        'items': [video(heroId, creatorOne, 'Waterside at dawn')],
        'next_cursor': null
      });
    }
    if (key == 'GET /videos/$heroId') {
      return ok(video(heroId, creatorOne, 'Waterside at dawn'));
    }
    final creator = RegExp(r'^GET /creators/([0-9a-f-]{36})$').firstMatch(key);
    if (creator != null) {
      return ok({
        'id': creator.group(1),
        'handle': creator.group(1) == creatorOne ? 'esi' : 'jslay',
        'display_name': creator.group(1) == creatorOne ? 'Esi' : 'J Slay',
        'bio': 'Stories',
        'location': 'Monrovia',
        'status': 'active',
        'follower_count': 7,
        'published_video_count': 2
      });
    }
    final follow =
        RegExp(r'^(GET|PUT|DELETE) /creators/([0-9a-f-]{36})/follow$')
            .firstMatch(key);
    if (follow != null) {
      if (follow.group(1) == 'PUT') followed = true;
      if (follow.group(1) == 'DELETE') followed = false;
      return ok({
        'creator_id': follow.group(2),
        'following': followed,
        'follower_count': followed ? 8 : 7
      });
    }
    final like = RegExp(r'^(GET|PUT|DELETE) /videos/([0-9a-f-]{36})/like$')
        .firstMatch(key);
    if (like != null) {
      if (like.group(1) == 'PUT') liked = true;
      if (like.group(1) == 'DELETE') liked = false;
      return ok({
        'video_id': like.group(2),
        'liked': liked,
        'like_count': liked ? 13 : 12
      });
    }
    if (key == 'GET /videos/$heroId/playback') {
      return ok({
        'playback_url': 'https://media.example.test/signed/video',
        'expires_at': DateTime.now()
            .toUtc()
            .add(const Duration(minutes: 5))
            .toIso8601String()
      });
    }
    if (key == 'POST /videos/$heroId/watch-sessions') {
      final expiry = DateTime.now()
          .toUtc()
          .add(const Duration(minutes: 5))
          .toIso8601String();
      return ok({
        'session_id': sessionId,
        'session_expires_at': expiry,
        'playback_url': 'https://media.example.test/signed/video',
        'playback_expires_at': expiry
      });
    }
    if (key == 'POST /reports') {
      return ok({
        'id': '00000000-0000-4000-8000-0000000000e1',
        'video_id': heroId,
        'status': 'open',
        'created_at': '2026-11-20T10:00:00Z'
      }, 201);
    }
    if (key == 'GET /creators/me/videos/$noticeVideo/notice') {
      return ok({
        'video_id': noticeVideo,
        'decision': 'removed',
        'reason_code': 'REVIEWED_REMOVE',
        'decided_at': '2026-10-28T12:00:00Z',
        'appealable': appealable,
        'appeal': null
      });
    }
    if (key == 'POST /videos/$noticeVideo/appeals') {
      return ok({
        'id': '00000000-0000-4000-8000-0000000000e2',
        'video_id': noticeVideo,
        'status': 'open',
        'created_at': '2026-11-20T10:00:00Z'
      }, 201);
    }
    if (key == 'GET /creators/me/points') {
      return ok({
        'creator_id': creatorOne,
        'balance': 1240,
        'currency': 'POINTS',
        'as_of': '2026-11-20T10:00:00Z',
        'confirmed': 1260,
        'pending': 160,
        'withheld': 40,
        'reversed': 20
      });
    }
    if (key == 'GET /creators/me/points/entries') {
      return ok({'items': [], 'next_cursor': null});
    }
    if (key == 'GET /creators/me/upload-eligibility') {
      return ok({'upload_eligible': true, 'creator_id': creatorOne});
    }
    return ok({'detail': 'unexpected $key'}, 404);
  }
}

void main() {
  late DesignCatalog catalog;
  setUpAll(() async {
    catalog = await DesignCatalog.load();
    await loadBrandFonts();
  });

  Future<(Gateway, MemoryStore)> boot(WidgetTester tester,
      {String? refresh = 'stored-refresh', int screen = 1}) async {
    useViewport(tester, AuditViewport.standard);
    final gateway = Gateway();
    final store = MemoryStore(refresh);
    final client = MockClient(gateway.handle);
    addTearDown(client.close);
    await tester.pumpWidget(KoloVibeApp(
        catalog: catalog,
        initialScreen: screen,
        dependencies: AppDependencies.live('https://api.example.test/api/v1',
            credentialStore: store, device: TestDevice(), client: client)));
    await settleAsync(tester);
    return (gateway, store);
  }

  Future<void> go(WidgetTester tester, int screen, {String? id}) async {
    final navigator =
        tester.state<NavigatorState>(find.byType(Navigator).first);
    final route = ScreenRoute(screen, entityId: id);
    navigator.pushNamed(route.name, arguments: route);
    await settleAsync(tester);
  }

  Future<void> tapText(WidgetTester tester, String text) async {
    final target = find.text(text).last;
    await tester.ensureVisible(target);
    await tester.pumpAndSettle();
    await tester.tap(target);
    await settleAsync(tester);
  }

  testWidgets('SEC-05 restore: one refresh, one /me, Home with the real name',
      (tester) async {
    final (gateway, store) = await boot(tester);
    expect(gateway.refreshes, 1);
    expect(gateway.meReads, 1, reason: 'Home must reuse the restored account');
    expect(store.value, 'rotated');
    expect(find.textContaining('Kofi Mensah'), findsOneWidget);
    expect(find.text('Waterside at dawn'), findsWidgets);
    expect(gateway.calls, contains('GET /videos/following'));
    expect(gateway.headers['GET /videos/following']!['Authorization'],
        'Bearer access');
    expect(
        gateway.headers['GET /videos']!.containsKey('Authorization'), isFalse,
        reason: 'public trending must not carry the account token');
  });

  testWidgets('no stored session opens Welcome, not Home and sends no token',
      (tester) async {
    final (gateway, _) = await boot(tester, refresh: null);
    expect(gateway.calls.where((c) => c.contains('/auth/refresh')), isEmpty);
    expect(find.textContaining('Kofi'), findsNothing);
  });

  testWidgets('Home Following See all opens the Following feed (M-018)',
      (tester) async {
    final (gateway, _) = await boot(tester);
    gateway.calls.clear();
    final seeAll = find.text('See all');
    expect(seeAll, findsNWidgets(2));
    await tester.ensureVisible(seeAll.last);
    await tester.pumpAndSettle();
    await tester.tap(seeAll.last);
    await settleBounded(tester);
    expect(gateway.calls, contains('GET /videos/following'));
    expect(find.text('Following'), findsWidgets);
    expect(find.text('For You'), findsOneWidget);
  });

  testWidgets('hero opens details; Play starts a tracked watch session',
      (tester) async {
    final (gateway, _) = await boot(tester);
    await tapText(tester, 'Waterside at dawn');
    expect(gateway.calls, contains('GET /videos/$heroId'));
    gateway.calls.clear();
    final play = find.text('Play original');
    await tester.ensureVisible(play);
    await tester.pumpAndSettle();
    await tester.tap(play);
    await settleBounded(tester);
    expect(gateway.calls, contains('POST /videos/$heroId/watch-sessions'));
    expect(
        gateway
            .headers['POST /videos/$heroId/watch-sessions']!['Authorization'],
        'Bearer access');
  });

  testWidgets('Like and Unlike send PUT and DELETE for the video',
      (tester) async {
    final (gateway, _) = await boot(tester);
    await tapText(tester, 'Waterside at dawn');
    expect(gateway.calls, contains('GET /videos/$heroId/like'));
    await tapText(tester, 'Like');
    expect(gateway.calls, contains('PUT /videos/$heroId/like'));
    expect(find.text('Unlike'), findsOneWidget);
    await tapText(tester, 'Unlike');
    expect(gateway.calls, contains('DELETE /videos/$heroId/like'));
  });

  testWidgets('Follow on Home sends PUT for that creator and can be undone',
      (tester) async {
    final (gateway, _) = await boot(tester);
    expect(gateway.calls, contains('GET /creators/$creatorOne/follow'));
    await tester.ensureVisible(find.text('Follow').first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Follow').first);
    await settleAsync(tester);
    expect(gateway.calls, contains('PUT /creators/$creatorOne/follow'));
    await tester.tap(find.widgetWithText(InkWell, 'Following').first);
    await settleAsync(tester);
    expect(gateway.calls, contains('DELETE /creators/$creatorOne/follow'));
  });

  testWidgets('Report sends the reason and details to POST /reports',
      (tester) async {
    final (gateway, _) = await boot(tester);
    await go(tester, 71, id: heroId);
    await tapText(tester, 'Rights or ownership concern');
    await tapText(tester, 'Continue');
    await tapText(tester, 'Submit report');
    final body = gateway.bodies['POST /reports']! as Map;
    expect(body['video_id'], heroId);
    expect(body['reason'], isNotEmpty);
    expect(gateway.headers['POST /reports']!['Idempotency-Key'], isNotEmpty);
  });

  testWidgets('Appeal reads the notice and posts the statement',
      (tester) async {
    final (gateway, _) = await boot(tester);
    await go(tester, 76, id: noticeVideo);
    expect(
        gateway.calls, contains('GET /creators/me/videos/$noticeVideo/notice'));
    await tapText(tester, 'Request a review');
    await tester.enterText(
        find.byType(TextFormField), 'The audio is licensed to me.');
    await tapText(tester, 'Send review request');
    expect(gateway.bodies['POST /videos/$noticeVideo/appeals'],
        {'reason': 'The audio is licensed to me.'});
  });

  testWidgets('an appeal is not offered when the server says it is not allowed',
      (tester) async {
    final (gateway, _) = await boot(tester);
    gateway.appealable = false;
    await go(tester, 78, id: noticeVideo);
    expect(find.text('Send review request'), findsNothing);
    expect(gateway.calls.where((c) => c.contains('/appeals')), isEmpty);
  });

  testWidgets('Lone Stars reads the creator balance and ledger',
      (tester) async {
    final (gateway, _) = await boot(tester);
    await go(tester, 61);
    expect(gateway.calls, contains('GET /creators/me/points'));
    expect(gateway.calls, contains('GET /creators/me/points/entries'));
    // The fake ledger is empty, so the screen shows the real empty state.
    expect(find.text('Your story starts here.'), findsOneWidget);
  });

  testWidgets('Create an original checks upload eligibility first',
      (tester) async {
    final (gateway, _) = await boot(tester);
    await go(tester, 41);
    expect(gateway.calls, contains('GET /creators/me/upload-eligibility'));
    expect(gateway.calls.where((c) => c.startsWith('POST /videos')), isEmpty,
        reason: 'no draft before the person chooses a file');
  });

  testWidgets('bottom tabs replace the screen instead of stacking',
      (tester) async {
    await boot(tester);
    final navigator =
        tester.state<NavigatorState>(find.byType(Navigator).first);
    for (final tab in ['Explore', 'Home', 'Explore', 'Home']) {
      await tester.tap(find.text(tab).last);
      await settleAsync(tester);
    }
    var depth = 0;
    navigator.popUntil((route) {
      depth++;
      return true;
    });
    expect(navigator.canPop(), isFalse,
        reason: 'tab switching must not build a back stack');
    expect(depth, 1);
  });
}
