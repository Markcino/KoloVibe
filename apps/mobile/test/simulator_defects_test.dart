import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/features/discovery/discovery_catalog_screen.dart';
import 'package:kolovibe/features/discovery/live_video_repository.dart';
import 'package:kolovibe/features/discovery/live_video_screen.dart';
import 'package:kolovibe/features/engagement/like_counts.dart';
import 'package:kolovibe/features/shell/main_shell.dart';
import 'fl_b_repositories_test.dart' show videoJson, videoId;
import 'fl_b_widgets_test.dart' show CatalogFixture, app, settle;

/// Regression tests for the 26 November simulator run (SIM-04 to SIM-10).
/// The SIM-01, SIM-08 and SIM-09 checks sit beside the screens they cover.
void main() {
  late DesignCatalog catalog;
  setUpAll(() async => catalog = await DesignCatalog.load());
  tearDown(LikeCounts.shared.reset);

  group('SIM-04 like counts across routes', () {
    test('the newest server answer wins', () {
      final counts = LikeCounts.shared;
      expect(counts.current(videoId, 12), 12);
      counts.confirm(videoId, 13);
      expect(counts.current(videoId, 12), 13);
      counts.supersede([videoId]);
      expect(counts.current(videoId, 14), 14);
    });

    test('a fetched video page supersedes an earlier confirmation', () async {
      LikeCounts.shared.confirm(videoId, 40);
      final repository =
          LiveVideoRepository(ApiClient('https://api.example.test/api/v1',
              client: MockClient((_) async => http.Response(
                  jsonEncode({
                    'items': [videoJson()],
                    'next_cursor': null
                  }),
                  200))));
      await repository.filteredPage();
      expect(LikeCounts.shared.current(videoId, 12), 12);
    });

    testWidgets('a like confirmed elsewhere updates a loaded list',
        (tester) async {
      final fixture = CatalogFixture(
          (_) async => LiveVideoPage([LiveVideo.fromJson(videoJson())], null));
      await tester.pumpWidget(app(DiscoveryCatalogScreen(
          screen: 22,
          repository: fixture,
          catalog: catalog,
          initialQuery: 'Waterside')));
      await settle(tester);
      expect(find.textContaining('12 likes'), findsOneWidget);
      LikeCounts.shared.confirm(videoId, 13);
      await tester.pump();
      expect(find.textContaining('13 likes'), findsOneWidget);
      expect(find.textContaining('12 likes'), findsNothing);
    });
  });

  group('SIM-05 search category stays visible', () {
    testWidgets('the carried category shows and can be removed',
        (tester) async {
      final calls = <Map<String, String?>>[];
      final fixture = CatalogFixture((q) async {
        calls.add(q);
        return q['category'] == null
            ? LiveVideoPage([LiveVideo.fromJson(videoJson())], null)
            : const LiveVideoPage([], null);
      });
      await tester.pumpWidget(app(DiscoveryCatalogScreen(
          screen: 22,
          repository: fixture,
          catalog: catalog,
          initialQuery: 'Waterside',
          initialCategory: 'comedy')));
      await settle(tester);
      expect(calls.last['category'], 'comedy');
      expect(find.text('Category: Comedy'), findsOneWidget);
      expect(find.textContaining('in Comedy'), findsOneWidget);
      await tester.tap(find.byTooltip('Remove category filter'));
      await settle(tester);
      expect(calls.last['category'], isNull);
      expect(find.text('Category: Comedy'), findsNothing);
      expect(find.textContaining('12 likes'), findsOneWidget);
    });
  });

  group('SIM-06 selected tab', () {
    testWidgets('Creator Studio keeps Create selected', (tester) async {
      final navigation = catalog[37].named('Primary navigation')!;
      await tester.pumpWidget(MaterialApp(
          home: Scaffold(
              bottomNavigationBar: MainShell(
                  navigation: navigation, screen: 37, onSelected: (_) {}))));
      final selected = tester
          .widgetList<Semantics>(find.byType(Semantics))
          .where((s) => s.properties.selected == true)
          .toList();
      expect(selected, hasLength(1));
      expect(
          find.descendant(
              of: find.byWidget(selected.single),
              matching: find.text('Create')),
          findsOneWidget);
    });
  });

  test('SIM-10 like counts are pluralised', () {
    expect(likeCountLabel(1), '1 like');
    expect(likeCountLabel(0), '0 likes');
    expect(likeCountLabel(2), '2 likes');
    expect(likeCountLabel(null), 'Likes unavailable');
  });
}
