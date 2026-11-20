import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/core/theme/kolovibe_theme.dart';
import 'package:kolovibe/features/creators/live_analytics_repository.dart';
import 'package:kolovibe/features/creators/live_analytics_screen.dart';

import 'fl_a_support.dart';
import 'support/audit_harness.dart';
import 'support/upload_fakes.dart' show videoId;

Map<String, Object?> creatorJson(String range,
        {int plays = 18200, int likes = 1826, int days = 7}) =>
    {
      'total_videos': 12,
      'videos_by_state': {},
      'range': range,
      'qualified_plays': plays,
      'watch_time_seconds': 2311200,
      'likes': likes,
      'new_followers': plays == 0 ? 0 : 184,
      'shares': plays == 0 ? 0 : 40,
      'daily': [
        for (var i = 0; i < days; i++)
          {
            'date': DateTime.utc(2026, 10, 1 + i)
                .toIso8601String()
                .substring(0, 10),
            'qualified_plays': plays == 0 ? 0 : plays ~/ days,
            'likes': likes == 0 ? 0 : likes ~/ days,
          }
      ],
      'top_videos': plays == 0
          ? []
          : [
              {
                'video_id': videoId,
                'title': 'Waterside at dawn',
                'qualified_plays': 12400
              }
            ],
    };

void main() {
  late DesignCatalog catalog;
  setUpAll(() async {
    catalog = await DesignCatalog.load();
    await loadBrandFonts();
  });

  group('repository', () {
    test('reads the creator summary for the requested range only', () async {
      final fixture = AccountFixture(
          handler: (request) async =>
              jsonResponse(creatorJson(request.url.queryParameters['range']!)));
      final data = await LiveAnalyticsRepository(fixture.account).creator('7d');
      expect(data.qualifiedPlays, 18200);
      expect(data.daily, hasLength(7));
      expect(data.top.single.title, 'Waterside at dawn');
      expect(
          fixture.requests.last.url.path, endsWith('/creators/me/analytics'));
      expect(fixture.requests.last.url.queryParameters, {'range': '7d'});
      await expectLater(LiveAnalyticsRepository(fixture.account).creator('1y'),
          throwsFormatException);
    });

    test('rejects a response for a different range or with bad numbers',
        () async {
      final wrongRange = AccountFixture(
          handler: (_) async => jsonResponse(creatorJson('28d', days: 28)));
      await expectLater(
          LiveAnalyticsRepository(wrongRange.account).creator('7d'),
          throwsFormatException);
      final negative = AccountFixture(
          handler: (_) async => jsonResponse(creatorJson('7d', likes: -1)));
      await expectLater(LiveAnalyticsRepository(negative.account).creator('7d'),
          throwsFormatException);
    });

    test('video analytics must name the requested video and range', () async {
      final fixture = AccountFixture(
          handler: (request) async => jsonResponse({
                'video_id': videoId,
                'state': 'published',
                'current_likes': 12,
                'qualified_viewers': 9,
                'range': request.url.queryParameters['range'],
                'qualified_plays': 10,
                'watch_time_seconds': 600,
                'likes': 3,
                'shares': 1,
                'average_watch_seconds': 60
              }));
      final repository = LiveAnalyticsRepository(fixture.account);
      final data = await repository.video(videoId, 'since_published');
      expect(data.averageWatchSeconds, 60);
      expect(fixture.requests.last.url.path,
          endsWith('/creators/me/videos/$videoId/analytics'));
      await expectLater(
          repository.video('not-an-id', '7d'), throwsFormatException);
      await expectLater(
          repository.video(videoId, '28d'), throwsFormatException);
    });
  });

  group('formatting', () {
    test('abbreviates counts and durations like the design', () {
      expect(analyticsCount(1826), '1,826');
      expect(analyticsCount(18200), '18.2K');
      expect(watchTime(2311200), '642h');
      expect(watchTime(90), '2m');
      expect(clockTime(127), '02:07');
      expect(chartDate(DateTime.utc(2026, 10, 21)), '21 OCT');
    });
  });

  group('screen', () {
    Future<AccountFixture> open(WidgetTester tester,
        {int? status, int plays = 18200}) async {
      useViewport(tester, AuditViewport.standard);
      final fixture = AccountFixture(handler: (request) async {
        if (status != null) return jsonResponse({'detail': 'x'}, status);
        final range = request.url.queryParameters['range']!;
        return jsonResponse(creatorJson(range,
            plays: plays,
            likes: plays == 0 ? 0 : 1826,
            days: range == '7d' ? 7 : 28));
      });
      await tester.pumpWidget(MaterialApp(
          theme: KoloVibeTheme.light(),
          home: LiveAnalyticsScreen(
              catalog: catalog,
              analytics: LiveAnalyticsRepository(fixture.account))));
      await settleAsync(tester);
      return fixture;
    }

    testWidgets('shows real totals and switches range', (tester) async {
      final fixture = await open(tester);
      expect(find.text('Stories that connect.'), findsOneWidget);
      expect(find.bySemanticsLabel('Qualified plays 18.2K'), findsOneWidget);
      expect(find.bySemanticsLabel('Likes 1,826'), findsOneWidget);
      await tester.tap(find.text('28 days'));
      await settleAsync(tester);
      expect(fixture.requests.last.url.queryParameters['range'], '28d');
    });

    testWidgets('no activity shows dashes, not zero performance (M-060)',
        (tester) async {
      await open(tester, plays: 0);
      expect(find.text('Every story starts somewhere.'), findsOneWidget);
      expect(find.text('—'), findsNWidgets(2));
      expect(find.text('0'), findsNothing);
    });

    for (final status in [403, 404, 503]) {
      testWidgets(
          'a closed or unavailable capability ($status) is a normal state',
          (tester) async {
        await open(tester, status: status);
        expect(find.text('Metrics unavailable'), findsOneWidget);
        expect(find.text('Try again'), findsOneWidget);
        expect(find.text('0'), findsNothing);
      });
    }

    testWidgets('an expired session offers sign-in rather than empty data',
        (tester) async {
      await open(tester, status: 401);
      expect(find.text('Metrics unavailable'), findsNothing);
      expect(find.text('Every story starts somewhere.'), findsNothing);
    });
  });
}
