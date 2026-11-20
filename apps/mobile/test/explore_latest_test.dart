import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/features/discovery/discovery_catalog_screen.dart';
import 'package:kolovibe/features/discovery/live_video_repository.dart';
import 'fl_a_support.dart';
import 'fl_b_repositories_test.dart' show videoJson, videoId;
import 'fl_b_widgets_test.dart' show CatalogFixture, app, settle;

/// D-4: M-019 shows the newest eligible original and never implies human curation.
void main() {
  late DesignCatalog catalog;
  setUpAll(() async => catalog = await DesignCatalog.load());
  const other = '00000000-0000-4000-8000-0000000000e1';
  const third = '00000000-0000-4000-8000-0000000000e2';

  testWidgets('the hero is the first (newest) record and is labelled Latest original',
      (tester) async {
    final calls = <Map<String, String?>>[];
    final fixture = CatalogFixture((q) async {
      calls.add(q);
      return LiveVideoPage([
        LiveVideo.fromJson({...videoJson(videoId), 'title': 'Newest piece'}),
        LiveVideo.fromJson({...videoJson(other), 'title': 'Second piece'}),
        LiveVideo.fromJson({...videoJson(third), 'title': 'Third piece'}),
      ], null);
    });
    await tester.pumpWidget(app(DiscoveryCatalogScreen(
        screen: 19,
        repository: fixture,
        catalog: catalog,
        account: AccountFixture().account)));
    await settle(tester);
    expect(calls.first['sort'], 'recent',
        reason: 'ordered by the service, never re-ranked on the phone');
    expect(find.text('LATEST ORIGINAL · CULTURE'), findsOneWidget);
    expect(find.text('Newest piece'), findsOneWidget);
    final all = tester
        .widgetList<Text>(find.byType(Text))
        .map((t) => (t.data ?? '').toLowerCase())
        .join(' | ');
    for (final banned in [
      'curated',
      'editor',
      'handpicked',
      'hand-picked',
      'staff pick',
      'featured by',
    ]) {
      expect(all.contains(banned), isFalse, reason: banned);
    }
  });

  testWidgets('a category without a label still reads Latest original',
      (tester) async {
    final fixture = CatalogFixture((q) async => LiveVideoPage([
          LiveVideo.fromJson({...videoJson(videoId), 'category': null}),
        ], null));
    await tester.pumpWidget(app(DiscoveryCatalogScreen(
        screen: 19, repository: fixture, catalog: catalog)));
    await settle(tester);
    expect(find.text('LATEST ORIGINAL'), findsOneWidget);
  });

  testWidgets('with no originals there is no hero and no curation claim',
      (tester) async {
    final fixture = CatalogFixture((q) async => const LiveVideoPage([], null));
    await tester.pumpWidget(app(DiscoveryCatalogScreen(
        screen: 19, repository: fixture, catalog: catalog)));
    await settle(tester);
    expect(find.textContaining('LATEST ORIGINAL'), findsNothing);
    expect(find.textContaining('urated'), findsNothing);
  });
}
