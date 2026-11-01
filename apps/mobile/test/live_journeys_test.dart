import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/app/screen_route.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/features/creators/live_creator_repository.dart';
import 'package:kolovibe/features/creators/live_creator_screen.dart';
import 'package:kolovibe/features/discovery/live_video_repository.dart';
import 'package:kolovibe/features/discovery/live_video_screen.dart';

class VideoPages extends LiveVideoRepository {
  VideoPages(this.fetch) : super(ApiClient('https://api.example.test/api/v1'));
  final Future<LiveVideoPage> Function(String?) fetch;

  @override
  Future<LiveVideoPage> page({String? cursor, String? creatorId}) =>
      fetch(cursor);
}

class CreatorResult extends LiveCreatorRepository {
  CreatorResult(this.fetch)
      : super(ApiClient('https://api.example.test/api/v1'));
  final Future<LiveCreator> Function() fetch;

  @override
  Future<LiveCreator> detail(String id) => fetch();
}

void main() {
  late DesignCatalog catalog;
  setUpAll(() async => catalog = await DesignCatalog.load());

  testWidgets(
      'pagination retains records after outage and retries the same cursor',
      (tester) async {
    final ids = List.generate(
        21,
        (index) =>
            '00000000-0000-4000-8000-${index.toString().padLeft(12, '0')}');
    var secondPageCalls = 0;
    final repository = VideoPages((cursor) async {
      if (cursor != null) {
        expect(cursor, ids[19]);
        secondPageCalls++;
        if (secondPageCalls == 1) throw const ApiFailure(503, 'Unavailable');
      }
      final indexes =
          cursor == null ? List.generate(20, (index) => index) : [20];
      return LiveVideoPage(
          indexes
              .map((index) => LiveVideo(
                  ids[index],
                  '00000000-0000-4000-8000-000000000099',
                  'Original $index',
                  ''))
              .toList(),
          cursor == null ? ids[19] : null);
    });
    await tester.pumpWidget(MaterialApp(
        home: LiveVideoScreen(
      route: const ScreenRoute(17),
      catalog: catalog,
      repository: repository,
    )));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('Load more'), 300);
    await tester.tap(find.text('Load more'));
    await tester.pumpAndSettle();
    expect(find.text('Original 19'), findsOneWidget);
    await tester.ensureVisible(find.text('Try again'));
    await tester.tap(find.text('Try again'));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('Original 20'), 150);
    expect(find.text('Original 20'), findsOneWidget);
    expect(secondPageCalls, 2);
    expect(tester.takeException(), isNull);
  });

  testWidgets('creator outage retries and public absence stays distinct',
      (tester) async {
    var status = 503;
    final repository =
        CreatorResult(() async => throw ApiFailure(status, 'Unavailable'));
    final semantics = tester.ensureSemantics();
    await tester.pumpWidget(MaterialApp(
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context)
            .copyWith(textScaler: const TextScaler.linear(2)),
        child: child!,
      ),
      home: LiveCreatorScreen(
        id: '00000000-0000-4000-8000-000000000001',
        repository: repository,
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Creators are temporarily unavailable.'), findsOneWidget);
    await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
    semantics.dispose();
    status = 404;
    await tester.tap(find.text('Try again'));
    await tester.pumpAndSettle();
    expect(find.text('This creator is not available for public viewing.'),
        findsOneWidget);
    expect(find.text('Try again'), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
