import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/app/screen_route.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/features/moderation/live_notice_screen.dart';
import 'package:kolovibe/features/moderation/live_standing_repository.dart';
import 'package:kolovibe/features/moderation/live_standing_screen.dart';

import 'support/standing_fakes.dart';
import 'support/upload_fakes.dart';

/// Widget tests with a scripted (fake) service and the real design catalog.
/// No HTTP, platform channels or device APIs are exercised.
void main() {
  late DesignCatalog catalog;
  late ScriptedStanding service;
  late List<RouteSettings> pushed;

  setUpAll(() async => catalog = await DesignCatalog.load());
  setUp(() {
    service = ScriptedStanding();
    pushed = [];
  });

  Future<void> pumpWidget(WidgetTester tester, Widget screen,
      {double textScale = 1}) async {
    // A tall surface keeps the whole notice built (it is a lazy list).
    tester.view.physicalSize = const Size(800, 3200);
    tester.view.devicePixelRatio = 2;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(const SizedBox());
    await tester.pumpWidget(MaterialApp(
      builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context)
              .copyWith(textScaler: TextScaler.linear(textScale)),
          child: child!),
      home: screen,
      onGenerateRoute: (settings) {
        pushed.add(settings);
        return MaterialPageRoute<void>(
            settings: settings,
            builder: (_) => const Scaffold(body: Text('next screen')));
      },
    ));
    await tester.pumpAndSettle();
  }

  Future<void> notice(WidgetTester tester,
          {String? entityId = videoId, double textScale = 1}) =>
      pumpWidget(
          tester,
          LiveNoticeScreen(
              route: ScreenRoute(76, entityId: entityId),
              catalog: catalog,
              repository: service),
          textScale: textScale);

  Future<void> standing(WidgetTester tester,
          {Future<Map<String, String>> Function(Set<String>)? titles,
          double textScale = 1}) =>
      pumpWidget(
          tester,
          LiveStandingScreen(
              catalog: catalog, repository: service, titleLookup: titles),
          textScale: textScale);

  ScreenRoute lastRoute() => pushed.last.arguments as ScreenRoute;

  Future<void> tapText(WidgetTester tester, String text) async {
    final finder = find.text(text);
    await tester.scrollUntilVisible(finder, 120,
        scrollable: find.byType(Scrollable).first);
    await tester.tap(finder);
    await tester.pumpAndSettle();
  }

  group('M-076 Content restriction notice', () {
    testWidgets('shows loading first', (tester) async {
      await tester.pumpWidget(MaterialApp(
          home: LiveNoticeScreen(
              route: const ScreenRoute(76, entityId: videoId),
              catalog: catalog,
              repository: service)));
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      await tester.pumpAndSettle();
    });

    testWidgets('a removal states what the server recorded, no more',
        (tester) async {
      service.noticeValue = videoNotice(code: 'REVIEWED_REMOVE');
      await notice(tester);
      expect(service.noticeReads, [videoId]);
      expect(find.text('Content availability has changed.'), findsOneWidget);
      expect(find.text('Removed'), findsOneWidget);
      expect(find.textContaining('Content notice · '), findsOneWidget);
      expect(
          find.text(
              'This content has been removed and is unavailable to viewers.'),
          findsOneWidget);
      expect(find.textContaining('No policy reason was specified'),
          findsOneWidget);
      expect(find.textContaining('Review options appear only when permitted'),
          findsOneWidget);
      // No invented policy label.
      expect(find.textContaining('Rights-related'), findsNothing);
    });

    testWidgets(
        'a non-default reason code is shown as received, never reworded',
        (tester) async {
      service.noticeValue =
          videoNotice(decision: 'restricted', code: 'COPYRIGHT_CLAIM');
      await notice(tester);
      expect(find.text('Restricted'), findsOneWidget);
      expect(find.text('This content is currently unavailable to viewers.'),
          findsOneWidget);
      expect(find.text('Reason code: COPYRIGHT_CLAIM'), findsOneWidget);
    });

    testWidgets('a missing reason code is stated', (tester) async {
      service.noticeValue = videoNotice(decision: 'rejected', code: null);
      await notice(tester);
      expect(find.text('This content wasn’t approved.'), findsOneWidget);
      expect(find.text('No reason code was recorded for this decision.'),
          findsOneWidget);
    });

    testWidgets('each decision has its own summary', (tester) async {
      for (final (decision, summary) in [
        ('rejected', 'not approved for publishing'),
        ('removed', 'has been removed'),
        ('restricted', 'currently unavailable'),
        ('restored', 'restored this content'),
      ]) {
        service.noticeValue = videoNotice(decision: decision);
        await notice(tester);
        expect(find.textContaining(summary), findsOneWidget, reason: decision);
      }
    });

    testWidgets('no decision says so and shows no reason', (tester) async {
      service.noticeValue = videoNotice(decision: 'none');
      await notice(tester);
      expect(find.text('No moderation decision.'), findsOneWidget);
      expect(find.text('Reason'), findsNothing);
      expect(find.textContaining('Content notice · '), findsNothing);
    });

    testWidgets(
        'an appealable removal is described and links to M-078; the notice itself sends nothing',
        (tester) async {
      service.noticeValue = videoNotice(appealable: true);
      await notice(tester);
      expect(
          find.textContaining('eligible for a review request'), findsOneWidget);
      expect(find.textContaining('not available in the app yet'), findsNothing);
      // The statement and the send action live on M-078, never on the notice.
      expect(find.byType(TextField), findsNothing);
      expect(
          find.widgetWithText(FilledButton, 'Request a review'), findsNothing);
      await tester.scrollUntilVisible(find.text('Request a review'), 200,
          scrollable: find.byType(Scrollable).first);
      expect(find.widgetWithText(OutlinedButton, 'Request a review'),
          findsOneWidget);
    });

    testWidgets('an existing review request shows its status and statement',
        (tester) async {
      for (final (status, text) in [
        ('open', 'under review'),
        ('denied', 'was denied'),
        ('restored', 'content was restored'),
      ]) {
        service.noticeValue = videoNotice(appeal: ownAppeal(status: status));
        await notice(tester);
        expect(find.text('Your review request'), findsOneWidget);
        expect(find.textContaining(text), findsOneWidget, reason: status);
        expect(find.text('The audio is licensed to me.'), findsOneWidget);
        expect(
            find.textContaining('eligible for a review request'), findsNothing);
      }
    });

    testWidgets('a non-appealable decision offers no review text',
        (tester) async {
      service.noticeValue = videoNotice(decision: 'rejected');
      await notice(tester);
      expect(
          find.textContaining('eligible for a review request'), findsNothing);
    });

    testWidgets('policy and help links open the info screens', (tester) async {
      await notice(tester);
      await tapText(tester, 'View policy information');
      expect(lastRoute().screen, 87);
      await notice(tester);
      await tapText(tester, 'Help & Support');
      expect(lastRoute().screen, 89);
    });

    testWidgets('someone else\'s or a missing video is "not found"',
        (tester) async {
      service.noticeFailure = const ApiFailure(404, 'Video not found');
      await notice(tester);
      expect(find.text('Not found'), findsOneWidget);
      expect(find.text('Removed'), findsNothing);
    });

    testWidgets('a non-creator is told notices are for the owner',
        (tester) async {
      service.noticeFailure = const ApiFailure(403, 'Creator role required');
      await notice(tester);
      expect(find.text('Not available'), findsOneWidget);
      expect(find.textContaining('only to the creator who owns the video'),
          findsOneWidget);
    });

    testWidgets('offline offers retry, which recovers', (tester) async {
      service.noticeFailure = const ApiFailure(503, 'down', offline: true);
      await notice(tester);
      expect(find.text('You are offline'), findsOneWidget);
      service.noticeFailure = null;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Content availability has changed.'), findsOneWidget);
    });

    testWidgets('an expired session offers sign-in', (tester) async {
      service.noticeFailure = const ApiFailure(401, 'Session expired');
      await notice(tester);
      await tester.tap(find.text('Sign in'));
      await tester.pumpAndSettle();
      expect(lastRoute().screen, 4);
    });

    testWidgets('no video id asks for one and reads nothing', (tester) async {
      await notice(tester, entityId: null);
      expect(find.text('Choose a video'), findsOneWidget);
      expect(service.noticeReads, isEmpty);
      await tester.tap(find.text('Open my video library'));
      await tester.pumpAndSettle();
      expect(lastRoute().screen, 40);
    });

    testWidgets('fits at 2.0 text scale', (tester) async {
      service.noticeValue = videoNotice(appealable: true, appeal: null);
      await notice(tester, textScale: 2);
      expect(tester.takeException(), isNull);
    });
  });

  group('M-077 Account status', () {
    testWidgets('an active publishing creator is not told anything alarming',
        (tester) async {
      await standing(tester);
      expect(find.text('Your creator account is active.'), findsOneWidget);
      expect(find.text('Publishing is available'), findsOneWidget);
      // SIM-08: the note's body does not repeat its title.
      expect(find.text('Publishing is available.'), findsNothing);
      expect(find.text('You can publish your originals.'), findsOneWidget);
      expect(find.text('No content notices.'), findsOneWidget);
      expect(find.textContaining('suspended'), findsNothing);
    });

    testWidgets('restricted and suspended use the designed restriction wording',
        (tester) async {
      for (final (status, headline) in [
        ('restricted', 'Your creator account is restricted.'),
        ('suspended', 'Your creator account is suspended.'),
      ]) {
        service.standingValue = AccountStanding(status, false, const []);
        await standing(tester);
        expect(find.text(headline), findsOneWidget, reason: status);
        expect(find.text('Publishing is unavailable'), findsOneWidget);
        expect(find.textContaining('cannot upload or publish'), findsOneWidget);
        expect(find.textContaining('restricted under the account policy'),
            findsOneWidget);
        // The server never reports a suspended *account* here.
        expect(find.text('Your account is suspended.'), findsNothing);
      }
    });

    testWidgets('pending creator and an active creator who cannot publish',
        (tester) async {
      service.standingValue = const AccountStanding('pending', false, []);
      await standing(tester);
      expect(
          find.text('Your creator profile is pending review.'), findsOneWidget);
      service.standingValue = const AccountStanding('active', false, []);
      await standing(tester);
      expect(find.textContaining('Publishing is unavailable right now'),
          findsOneWidget);
    });

    testWidgets('a viewer is offered the way to become a creator',
        (tester) async {
      service.standingValue = const AccountStanding(null, false, []);
      await standing(tester);
      expect(find.text('You don’t have a creator profile.'), findsOneWidget);
      expect(find.text('Content notices'), findsNothing);
      await tester.tap(find.text('Become a creator'));
      await tester.pumpAndSettle();
      expect(lastRoute().screen, 36);
    });

    testWidgets('notices list the decision, date and named video',
        (tester) async {
      service.standingValue = AccountStanding('active', true, [
        videoNotice(),
        videoNotice(video: videoIdFor(2), decision: 'restricted'),
      ]);
      await standing(tester,
          titles: (_) async => {videoId: 'Waterside at dawn'});
      expect(find.text('Waterside at dawn'), findsOneWidget);
      // The second video has no known title: shown unnamed, not invented.
      expect(find.text('Content notice'), findsOneWidget);
      expect(find.textContaining('Removed · '), findsOneWidget);
      expect(find.textContaining('Restricted · '), findsOneWidget);
    });

    testWidgets('opening a notice carries the video id to M-076',
        (tester) async {
      service.standingValue = AccountStanding('active', true, [videoNotice()]);
      await standing(tester);
      await tapText(tester, 'Content notice');
      expect(lastRoute().screen, 76);
      expect(lastRoute().entityId, videoId);
    });

    testWidgets('offers no account-level notice that has no contract',
        (tester) async {
      await standing(tester);
      expect(find.text('View account notice'), findsNothing);
      expect(find.text('Review the account notice'), findsNothing);
    });

    testWidgets('offline retries, expired signs in', (tester) async {
      service.standingFailure = const ApiFailure(503, 'down', offline: true);
      await standing(tester);
      expect(find.text('You are offline'), findsOneWidget);
      service.standingFailure = null;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Your creator account is active.'), findsOneWidget);
      service.standingFailure = const ApiFailure(401, 'Session expired');
      await standing(tester);
      await tester.tap(find.text('Sign in'));
      await tester.pumpAndSettle();
      expect(lastRoute().screen, 4);
    });

    testWidgets('policy and help links open the info screens', (tester) async {
      await standing(tester);
      await tapText(tester, 'View policy information');
      expect(lastRoute().screen, 87);
      await standing(tester);
      await tapText(tester, 'Help & Support');
      expect(lastRoute().screen, 89);
    });

    testWidgets('pull to refresh reads standing again', (tester) async {
      await standing(tester);
      expect(service.standingReads, 1);
      service.standingValue = const AccountStanding('restricted', false, []);
      await tester.fling(
          find.byType(Scrollable).first, const Offset(0, 400), 1000);
      await tester.pumpAndSettle();
      expect(service.standingReads, 2);
      expect(find.text('Your creator account is restricted.'), findsOneWidget);
    });

    testWidgets('fits at 2.0 text scale with notices', (tester) async {
      service.standingValue =
          AccountStanding('restricted', false, [videoNotice()]);
      await standing(tester, textScale: 2);
      expect(tester.takeException(), isNull);
    });
  });
}
