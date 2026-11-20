import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/features/discovery/live_video_screen.dart';
import 'package:kolovibe/features/discovery/slow_connection_sheet.dart';
import 'fl_b_repositories_test.dart' show videoId;
import 'fl_b_widgets_test.dart' show FakePlayer, PlayerFixture, app, settle;

/// D-3: M-034 is a truthful slow-connection state. R1 has one rendition, so no Data Saver.
void main() {
  Future<(PlayerFixture, FakePlayer, FakePlayer, List<int>)> open(
      WidgetTester tester,
      {bool fullScreen = true}) async {
    final repository = PlayerFixture();
    final first = FakePlayer()..pending = Completer<void>();
    final second = FakePlayer();
    final attempts = <int>[];
    await tester.pumpWidget(app(LiveVideoDetailScreen(
        id: videoId,
        repository: repository,
        fullScreen: fullScreen,
        playerFactory: (_) {
          attempts.add(attempts.length);
          return attempts.length == 1 ? first : second;
        })));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    if (!fullScreen) {
      final play = find.text('Play original');
      await tester.ensureVisible(play);
      await tester.tap(play);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
    }
    // Whatever the test did, end with nothing pending: release the held player and the 15 s guard.
    addTearDown(() {
      if (first.pending != null && !first.pending!.isCompleted) {
        first.pending!.complete();
      }
    });
    return (repository, first, second, attempts);
  }

  Future<void> press(WidgetTester tester, String label) async {
    final target = find.text(label);
    await tester.ensureVisible(target);
    await tester.pump();
    await tester.tap(target);
  }

  Future<void> finish(WidgetTester tester) async {
    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(seconds: 20));
  }

  String allText(WidgetTester tester) => tester
      .widgetList<Text>(find.byType(Text))
      .map((t) => t.data ?? t.textSpan?.toPlainText() ?? '')
      .join(' | ')
      .toLowerCase();

  for (final fullScreen in [true, false]) {
    group(fullScreen ? 'full-screen player' : 'detail page', () {
      testWidgets('after five seconds it explains the slow connection honestly',
          (tester) async {
        await open(tester, fullScreen: fullScreen);
        expect(find.byType(SlowConnectionSheet), findsNothing);
        await tester.pump(const Duration(seconds: 5));
        expect(find.byType(SlowConnectionSheet), findsOneWidget);
        expect(find.text('Your connection is slow.'), findsOneWidget);
        expect(find.text('Try again'), findsOneWidget);
        expect(find.text('Keep waiting'), findsOneWidget);
        expect(find.textContaining('Normal carrier data charges apply'),
            findsOneWidget);
        final text = allText(tester);
        for (final banned in [
          'data saver',
          'lower-data',
          'lower data',
          'smaller',
          'switch to a lower',
          'adapts',
          'quality adapts',
        ]) {
          expect(text.contains(banned), isFalse, reason: banned);
        }
        expect(find.byType(Switch), findsNothing);
        expect(find.byType(SwitchListTile), findsNothing);
        expect(find.byType(Checkbox), findsNothing);
        await finish(tester);
      });

      testWidgets('Keep waiting hides the sheet and keeps loading',
          (tester) async {
        final (repository, first, _, _) =
            await open(tester, fullScreen: fullScreen);
        await tester.pump(const Duration(seconds: 5));
        await press(tester, 'Keep waiting');
        await tester.pump();
        expect(find.byType(SlowConnectionSheet), findsNothing);
        expect(find.textContaining('Still loading on a slow connection'),
            findsOneWidget);
        expect(repository.grants, 1, reason: 'no new request was made');
        expect(first.disposed, isFalse);
        await finish(tester);
      });

      testWidgets('Try again starts a fresh attempt and abandons the old one',
          (tester) async {
        final (repository, first, second, attempts) =
            await open(tester, fullScreen: fullScreen);
        await tester.pump(const Duration(seconds: 5));
        await press(tester, 'Try again');
        await settle(tester);
        expect(repository.grants, 2);
        expect(attempts.length, 2);
        expect(find.byType(SlowConnectionSheet), findsNothing);
        // The abandoned attempt finishes late: it must not take over or leave a controller behind.
        first.pending!.complete();
        await settle(tester);
        expect(first.disposed, isTrue);
        expect(second.disposed, isFalse);
        expect(second.value.isInitialized, isTrue);
        await tester.pumpWidget(const SizedBox());
        await settle(tester);
        expect(second.disposed, isTrue);
        await finish(tester);
      });

      testWidgets('a late failure of the abandoned attempt shows no error',
          (tester) async {
        final (_, first, second, _) =
            await open(tester, fullScreen: fullScreen);
        await tester.pump(const Duration(seconds: 5));
        await press(tester, 'Try again');
        await settle(tester);
        first
          ..fail = true
          ..pending!.complete();
        await settle(tester);
        expect(find.byKey(const ValueKey('M-033')), findsNothing);
        expect(second.value.isInitialized, isTrue);
        await finish(tester);
      });
    });
  }

  testWidgets('the sheet fits a small phone at 2x text', (tester) async {
    tester.view.physicalSize = const Size(375 * 2, 667 * 2);
    tester.view.devicePixelRatio = 2;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(MaterialApp(
        builder: (context, child) => MediaQuery(
            data: MediaQuery.of(context).copyWith(
                textScaler: const TextScaler.linear(2)),
            child: child!),
        home: Scaffold(
            body: SingleChildScrollView(
                child: SlowConnectionSheet(
                    onRetry: () {}, onKeepWaiting: () {})))));
    await tester.pump();
    expect(tester.takeException(), isNull);
    expect(find.text('Try again'), findsOneWidget);
  });
}
