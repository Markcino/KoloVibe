import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/app/screen_route.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/features/moderation/live_report_screen.dart';

import 'support/report_fakes.dart';
import 'support/upload_fakes.dart';

/// Widget tests with scripted (fake) services and the real design catalog.
/// No HTTP, platform channels or device APIs are exercised.
void main() {
  late DesignCatalog catalog;
  late ScriptedVideos videos;
  late ScriptedModeration moderation;
  late List<RouteSettings> pushed;

  setUpAll(() async => catalog = await DesignCatalog.load());
  setUp(() {
    videos = ScriptedVideos();
    moderation = ScriptedModeration();
    pushed = [];
  });

  Future<void> pump(WidgetTester tester, int screen,
      {String? entityId = videoId, double textScale = 1}) async {
    await tester.pumpWidget(const SizedBox());
    await tester.pumpWidget(MaterialApp(
      builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context)
              .copyWith(textScaler: TextScaler.linear(textScale)),
          child: child!),
      home: LiveReportScreen(
          route: ScreenRoute(screen, entityId: entityId),
          catalog: catalog,
          videos: videos,
          moderation: moderation),
      onGenerateRoute: (settings) {
        pushed.add(settings);
        return MaterialPageRoute<void>(
            settings: settings,
            builder: (_) => const Scaffold(body: Text('next screen')));
      },
    ));
    await tester.pumpAndSettle();
  }

  ScreenRoute lastRoute() => pushed.last.arguments as ScreenRoute;

  Future<void> tapText(WidgetTester tester, String text) async {
    final finder = find.text(text);
    if (find.byType(Scrollable).evaluate().isNotEmpty) {
      await tester.scrollUntilVisible(finder, 120,
          scrollable: find.byType(Scrollable).first);
    }
    // Bring the whole control clear of the bottom navigation before tapping.
    await tester.ensureVisible(finder);
    await tester.pumpAndSettle();
    await tester.tap(finder);
    await tester.pumpAndSettle();
  }

  /// Picks the rights concern and opens the details step.
  Future<void> toDetails(WidgetTester tester,
      {String reason = 'Rights or ownership concern'}) async {
    await tapText(tester, reason);
    await tapText(tester, 'Continue');
  }

  group('M-071 Report a video', () {
    testWidgets('loads the video, then lists the six reasons', (tester) async {
      await tester.pumpWidget(MaterialApp(
          home: LiveReportScreen(
              route: const ScreenRoute(71, entityId: videoId),
              catalog: catalog,
              videos: videos,
              moderation: moderation)));
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      await tester.pumpAndSettle();
      expect(find.text('Waterside at dawn'), findsOneWidget);
      expect(find.text('Reporting privately'), findsOneWidget);
      expect(find.text('What’s your concern?'), findsOneWidget);
      for (final label in [
        'Harassment or hateful content',
        'Violence or harmful activity',
        'Sexual or inappropriate content',
        'Rights or ownership concern',
        'Spam or misleading content',
        'Something else',
      ]) {
        expect(find.text(label), findsOneWidget, reason: label);
      }
    });

    testWidgets('Continue is off until a reason is chosen, and nothing is sent',
        (tester) async {
      await pump(tester, 71);
      expect(
          tester
              .widget<FilledButton>(
                  find.widgetWithText(FilledButton, 'Continue'))
              .onPressed,
          isNull);
      await tapText(tester, 'Something else');
      expect(
          tester
              .widget<FilledButton>(
                  find.widgetWithText(FilledButton, 'Continue'))
              .onPressed,
          isNotNull);
      expect(moderation.submissions, isEmpty);
    });

    testWidgets('a video that is gone says so and offers a way out',
        (tester) async {
      videos.failure = const ApiFailure(404, 'Not found');
      await pump(tester, 71);
      expect(find.text('Video not available'), findsOneWidget);
      await tester.tap(find.text('Return to videos'));
      await tester.pumpAndSettle();
      expect(lastRoute().screen, 24);
    });

    testWidgets('offline shows retry, and retry recovers', (tester) async {
      videos.failure = offlineReport;
      await pump(tester, 71);
      expect(find.text('You are offline'), findsOneWidget);
      videos.failure = null;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('What’s your concern?'), findsOneWidget);
    });

    testWidgets('an expired session offers sign-in', (tester) async {
      videos.failure = expiredReport;
      await pump(tester, 71);
      expect(find.text('Session expired'), findsOneWidget);
      await tester.tap(find.text('Sign in'));
      await tester.pumpAndSettle();
      expect(lastRoute().screen, 4);
    });

    testWidgets('no video id asks the person to choose a video',
        (tester) async {
      await pump(tester, 71, entityId: null);
      expect(find.text('Choose a video before reporting.'), findsOneWidget);
      expect(videos.reads, 0);
    });
  });

  group('M-072 Report details', () {
    testWidgets('shows the chosen reason, optional text and the privacy note',
        (tester) async {
      await pump(tester, 71);
      await toDetails(tester);
      expect(find.text('Report details'), findsOneWidget);
      expect(find.widgetWithText(Chip, 'Rights or ownership concern'),
          findsOneWidget);
      expect(find.text('Additional details · Optional'), findsOneWidget);
      expect(find.textContaining('Your report is private'), findsOneWidget);
      expect(find.textContaining('does not automatically remove content'),
          findsOneWidget);
    });

    testWidgets('submits the code, trimmed text and one key', (tester) async {
      await pump(tester, 71);
      await toDetails(tester);
      await tester.enterText(find.byType(TextField), '  audio is unlicensed ');
      await tapText(tester, 'Submit report');
      final sent = moderation.submissions.single;
      expect(sent.videoId, videoId);
      expect(sent.reason, 'copyright');
      expect(sent.details, 'audio is unlicensed');
      expect(sent.key.length, greaterThanOrEqualTo(16));
    });

    testWidgets('back returns to the reasons without losing the choice',
        (tester) async {
      await pump(tester, 71);
      await toDetails(tester);
      await tester.tap(find.byTooltip('Back'));
      await tester.pumpAndSettle();
      expect(find.text('What’s your concern?'), findsOneWidget);
      await tapText(tester, 'Continue');
      expect(find.widgetWithText(Chip, 'Rights or ownership concern'),
          findsOneWidget);
    });

    testWidgets('a cold M-072 starts at the reasons (a reason is required)',
        (tester) async {
      await pump(tester, 72);
      expect(find.text('What’s your concern?'), findsOneWidget);
      expect(find.byType(TextField), findsNothing);
    });

    testWidgets('the text field caps at 2000 characters', (tester) async {
      await pump(tester, 71);
      await toDetails(tester);
      await tester.enterText(find.byType(TextField), 'x' * 2100);
      await tester.pump();
      expect(tester.widget<TextField>(find.byType(TextField)).maxLength, 2000);
      final text = tester.widget<TextField>(find.byType(TextField));
      expect(text.controller!.text.length, 2000);
    });
  });

  group('M-073 Report submitted', () {
    testWidgets('shows the server receipt and promises no removal',
        (tester) async {
      await pump(tester, 71);
      await toDetails(tester);
      await tapText(tester, 'Submit report');
      expect(find.text('Report submitted'), findsOneWidget);
      expect(find.text('Thank you for speaking up.'), findsOneWidget);
      expect(
          find.textContaining('has been submitted for review'), findsOneWidget);
      expect(find.text('Reported privately · Rights concern'), findsOneWidget);
      expect(find.textContaining('doesn’t automatically remove a video'),
          findsOneWidget);
    });

    testWidgets('the sent text is cleared from the screen', (tester) async {
      await pump(tester, 71);
      await toDetails(tester);
      await tester.enterText(find.byType(TextField), 'private words');
      await tapText(tester, 'Submit report');
      expect(find.text('private words'), findsNothing);
    });

    testWidgets('links lead to the video list and the guidelines',
        (tester) async {
      await pump(tester, 71);
      await toDetails(tester);
      await tapText(tester, 'Submit report');
      await tapText(tester, 'Return to videos');
      expect(lastRoute().screen, 24);
      expect(lastRoute().entityId, isNull);
      await pump(tester, 71);
      await toDetails(tester);
      await tapText(tester, 'Submit report');
      await tapText(tester, 'Read community guidelines');
      expect(lastRoute().screen, 87);
    });

    testWidgets('a cold M-073 shows the latest report for the video',
        (tester) async {
      moderation.reports = [ownReport(1, status: 'resolved', reason: 'spam')];
      await pump(tester, 73);
      expect(find.text('Report submitted'), findsOneWidget);
      expect(find.text('Reported privately · Spam concern'), findsOneWidget);
      expect(find.textContaining('has been reviewed'), findsOneWidget);
    });

    testWidgets('a cold M-073 with no report offers the reasons instead',
        (tester) async {
      await pump(tester, 73);
      expect(find.text('Thank you for speaking up.'), findsNothing);
      expect(find.text('What’s your concern?'), findsOneWidget);
    });
  });

  group('M-074 Report submission error', () {
    testWidgets('an unconfirmed report keeps the text and retries safely',
        (tester) async {
      await pump(tester, 71);
      await toDetails(tester);
      await tester.enterText(find.byType(TextField), 'keep this');
      moderation.failures.add(offlineReport);
      await tapText(tester, 'Submit report');
      expect(find.text('Report submission error'), findsOneWidget);
      expect(find.text('Report not confirmed'), findsOneWidget);
      expect(find.text('We couldn’t send your report.'), findsOneWidget);
      expect(
          find.textContaining('did not confirm your report'), findsOneWidget);
      expect(find.text('Rights or ownership concern'), findsOneWidget);
      expect(find.text('Report submitted'), findsNothing);
      await tapText(tester, 'Try submitting again');
      expect(find.text('Report submitted'), findsOneWidget);
      expect(moderation.submissions.map((s) => s.key).toSet(), hasLength(1));
      expect(moderation.submissions.every((s) => s.details == 'keep this'),
          isTrue);
    });

    testWidgets('return to details shows the typed text again', (tester) async {
      await pump(tester, 71);
      await toDetails(tester);
      await tester.enterText(find.byType(TextField), 'keep this');
      moderation.failures.add(offlineReport);
      await tapText(tester, 'Submit report');
      await tapText(tester, 'Return to report details');
      expect(find.text('keep this'), findsOneWidget);
    });

    testWidgets('cancel leaves the report', (tester) async {
      await tester.pumpWidget(MaterialApp(
          home: Builder(
              builder: (context) => Scaffold(
                  body: TextButton(
                      onPressed: () => Navigator.of(context).push(
                          MaterialPageRoute<void>(
                              builder: (_) => LiveReportScreen(
                                  route:
                                      const ScreenRoute(71, entityId: videoId),
                                  catalog: catalog,
                                  videos: videos,
                                  moderation: moderation))),
                      child: const Text('open report'))))));
      await tester.tap(find.text('open report'));
      await tester.pumpAndSettle();
      await toDetails(tester);
      moderation.failures.add(offlineReport);
      await tapText(tester, 'Submit report');
      await tapText(tester, 'Cancel report');
      expect(find.text('Report submission error'), findsNothing);
      expect(find.text('open report'), findsOneWidget);
    });

    testWidgets('an expired session offers sign-in and no retry',
        (tester) async {
      await pump(tester, 71);
      await toDetails(tester);
      moderation.failures.add(expiredReport);
      await tapText(tester, 'Submit report');
      expect(find.textContaining('Your report was not sent'), findsOneWidget);
      expect(find.text('Try submitting again'), findsNothing);
      await tapText(tester, 'Sign in');
      expect(lastRoute().screen, 4);
    });

    testWidgets('a refusal or missing video offers no retry', (tester) async {
      for (final (failure, text) in [
        (const ApiFailure(403, 'Forbidden'), 'You can’t report this video'),
        (const ApiFailure(404, 'Not found'), 'no longer available to report'),
      ]) {
        await pump(tester, 71);
        await toDetails(tester);
        moderation.failures.add(failure);
        await tapText(tester, 'Submit report');
        expect(find.textContaining(text), findsOneWidget);
        expect(find.text('Try submitting again'), findsNothing);
        expect(find.text('Report submitted'), findsNothing);
      }
    });

    testWidgets('the submit button is disabled while sending', (tester) async {
      await pump(tester, 71);
      await toDetails(tester);
      final gate = moderation.gate = Completer<void>();
      await tester.tap(find.text('Submit report'));
      await tester.pump();
      final button = tester.widget<FilledButton>(
          find.widgetWithText(FilledButton, 'Submitting…'));
      expect(button.onPressed, isNull);
      gate.complete();
      await tester.pumpAndSettle();
      expect(moderation.submissions, hasLength(1));
    });
  });

  group('M-075 Already reported', () {
    testWidgets('a duplicate is shown as already recorded, not an error',
        (tester) async {
      moderation.reports = [ownReport(1, reason: 'copyright')];
      await pump(tester, 71);
      await toDetails(tester);
      moderation.failures.add(alreadyReported);
      await tapText(tester, 'Submit report');
      expect(find.text('Already reported'), findsOneWidget);
      expect(find.text('Your concern is already recorded.'), findsOneWidget);
      expect(find.text('Previously reported · Rights concern'), findsOneWidget);
      expect(find.text('No duplicate report was created'), findsOneWidget);
      expect(find.textContaining('determined separately'), findsOneWidget);
      expect(find.text('Report submission error'), findsNothing);
    });

    testWidgets('without the earlier report the notice still shows',
        (tester) async {
      moderation.listFailure = offlineReport;
      await pump(tester, 71);
      await toDetails(tester);
      moderation.failures.add(alreadyReported);
      await tapText(tester, 'Submit report');
      expect(find.text('Previously reported'), findsWidgets);
      expect(find.textContaining('· '), findsNothing);
    });

    testWidgets('a cold M-075 finds an open report on a later page',
        (tester) async {
      moderation = ScriptedModeration(pageSize: 1)
        ..reports = [
          ownReport(1, video: '00000000-0000-4000-8000-000000000099'),
          ownReport(2, video: '00000000-0000-4000-8000-000000000098'),
          ownReport(3, reason: 'spam'),
        ];
      await pump(tester, 75);
      expect(find.text('Your concern is already recorded.'), findsOneWidget);
      expect(find.text('Previously reported · Spam concern'), findsOneWidget);
      expect(moderation.listReads, 3);
    });

    testWidgets('a lookup failure is a retryable state', (tester) async {
      moderation.listFailure = offlineReport;
      await pump(tester, 75);
      expect(find.text('You are offline'), findsOneWidget);
      moderation
        ..listFailure = null
        ..reports = [ownReport(1)];
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Your concern is already recorded.'), findsOneWidget);
    });
  });

  group('layout and safety', () {
    testWidgets('every step fits at 2.0 text scale', (tester) async {
      await pump(tester, 71, textScale: 2);
      expect(tester.takeException(), isNull);
      await toDetails(tester);
      expect(tester.takeException(), isNull);
      moderation.failures.add(offlineReport);
      await tapText(tester, 'Submit report');
      expect(tester.takeException(), isNull);
      await tapText(tester, 'Try submitting again');
      expect(tester.takeException(), isNull);
    });

    testWidgets('the report screens never claim a video was removed',
        (tester) async {
      await pump(tester, 71);
      await toDetails(tester);
      await tapText(tester, 'Submit report');
      expect(find.textContaining(RegExp(r'was removed|has been removed')),
          findsNothing);
    });
  });
}
