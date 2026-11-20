import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/core/theme/kolovibe_theme.dart';
import 'package:kolovibe/features/content/live_content_repository.dart';
import 'package:kolovibe/features/content/live_manage_video_screen.dart';
import 'support/audit_harness.dart';
import 'support/upload_fakes.dart';

class _Repo extends LiveContentRepository {
  _Repo(this.video) : super(unusedAccount());
  OwnedVideo video;
  int? savedCover;
  @override
  Future<OwnedVideo> ownedVideo(String id) async => video;
  @override
  Future<OwnedVideo> editDetails(OwnedVideo v,
      {String? title,
      String? description,
      String? category,
      List<String>? tags,
      int? coverTimeMs}) async {
    savedCover = coverTimeMs;
    return video = OwnedVideo(
        v.id, v.creatorId, v.title, v.description, v.state, v.createdAt,
        visibility: v.visibility,
        category: v.category,
        durationMs: v.durationMs,
        coverTimeMs: coverTimeMs,
        revision: v.revision);
  }
}

OwnedVideo _video({int? durationMs}) => OwnedVideo(videoId, creatorId,
    'Waterside at dawn', 'A story', 'published', DateTime.utc(2026, 11, 11),
    visibility: 'private',
    category: 'short_films',
    durationMs: durationMs,
    revision: 4);

void main() {
  Future<_Repo> open(WidgetTester tester, OwnedVideo video) async {
    useViewport(tester, AuditViewport.small, textScale: 1);
    final repo = _Repo(video);
    await tester.pumpWidget(MaterialApp(
        theme: KoloVibeTheme.light(),
        home: LiveManageVideoScreen(videoId: videoId, repository: repo)));
    await settleAsync(tester);
    await tester.tap(find.text('Edit details'));
    await settleAsync(tester);
    return repo;
  }

  testWidgets('a processed video offers a cover moment that is saved',
      (tester) async {
    final repo = await open(tester, _video(durationMs: 90000));
    final slider = find.byKey(const ValueKey('Cover moment'));
    expect(slider, findsOneWidget);
    expect(find.textContaining('of 1:30'), findsOneWidget);
    await tester.drag(slider, const Offset(120, 0));
    await tester.pump();
    await tester.tap(find.text('Save'));
    await settleAsync(tester);
    expect(repo.savedCover, isNotNull);
    expect(repo.savedCover, greaterThan(0));
    expect(repo.savedCover, lessThanOrEqualTo(90000));
  });

  testWidgets('without a known duration no cover control is shown',
      (tester) async {
    await open(tester, _video());
    expect(find.byKey(const ValueKey('Cover moment')), findsNothing);
  });
}
