import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:kolovibe/app/screen_route.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/core/theme/kolovibe_theme.dart';
import 'package:kolovibe/features/moderation/live_appeal_screen.dart';
import 'package:kolovibe/features/moderation/live_moderation_repository.dart';
import 'package:kolovibe/features/moderation/live_notice_screen.dart';
import 'fl_a_support.dart' hide accountId;
import 'support/audit_harness.dart';
import 'support/standing_fakes.dart';
import 'support/upload_fakes.dart';

void main() {
  late DesignCatalog catalog;
  setUpAll(() async {
    catalog = await DesignCatalog.load();
    await loadBrandFonts();
  });

  final pushed = <RouteSettings>[];
  Widget host(Widget child) => MaterialApp(
      key: UniqueKey(),
      theme: KoloVibeTheme.light(),
      home: child,
      onGenerateRoute: (settings) {
        pushed.add(settings);
        return MaterialPageRoute<void>(
            settings: settings,
            builder: (_) => const Scaffold(body: Text('next screen')));
      });

  /// A moderation repository over a recording HTTP gateway.
  ({LiveModerationRepository repo, List<http.Request> requests}) gateway(
      {int status = 201}) {
    final fixture = AccountFixture(handler: (request) async {
      if (request.url.path.endsWith('/appeals')) {
        return jsonResponse({
          'id': '00000000-0000-4000-8000-000000000a01',
          'video_id': videoId,
          'status': 'open',
          'created_at': '2026-11-20T10:00:00Z',
        }, status);
      }
      return jsonResponse({});
    });
    return (
      repo: LiveModerationRepository(fixture.account),
      requests: fixture.requests
    );
  }

  Future<void> pump(WidgetTester tester, ScriptedStanding standing,
      LiveModerationRepository moderation) async {
    useViewport(tester, AuditViewport.standard);
    pushed.clear();
    await tester.pumpWidget(host(LiveAppealScreen(
        route: const ScreenRoute(78, entityId: videoId),
        catalog: catalog,
        standing: standing,
        moderation: moderation)));
    await settleAsync(tester);
  }

  testWidgets('without eligibility the screen offers no submit control',
      (tester) async {
    final g = gateway();
    await pump(tester, ScriptedStanding()..noticeValue = videoNotice(), g.repo);
    expect(find.text('Appeal availability not confirmed'), findsOneWidget);
    expect(find.text('Review request unavailable'), findsOneWidget);
    expect(find.text('Send review request'), findsNothing);
    expect(find.byType(TextFormField), findsNothing);
    expect(g.requests.where((r) => r.url.path.endsWith('/appeals')), isEmpty);
  });

  testWidgets(
      'an eligible decision sends the statement to the appeals endpoint',
      (tester) async {
    final g = gateway();
    final standing = ScriptedStanding()
      ..noticeValue = videoNotice(appealable: true);
    await pump(tester, standing, g.repo);
    expect(find.text('Send review request'), findsOneWidget);
    // Too short: refused locally, nothing sent.
    await tester.enterText(find.byType(TextFormField), 'short');
    await tester.tap(find.text('Send review request'));
    await settleAsync(tester);
    expect(find.text('Write at least 10 characters.'), findsOneWidget);
    expect(g.requests.where((r) => r.url.path.endsWith('/appeals')), isEmpty);

    await tester.enterText(
        find.byType(TextFormField), 'The audio is licensed to me.');
    // The notice is read again after sending and now carries the request.
    standing.noticeValue = videoNotice(appeal: ownAppeal());
    await tester.tap(find.text('Send review request'));
    await settleAsync(tester);
    final post = g.requests.singleWhere((r) => r.url.path.endsWith('/appeals'));
    expect(post.url.path, endsWith('/videos/$videoId/appeals'));
    expect(jsonDecode(post.body), {'reason': 'The audio is licensed to me.'});
    expect(find.text('Send review request'), findsNothing);
    expect(find.byKey(const ValueKey('appeal-receipt')), findsOneWidget);
    expect(find.text('Review request received.'), findsOneWidget);
    expect(find.text('00000000-0000-4000-8000-000000000a01'), findsOneWidget);
    expect(find.text('20 Nov 2026, 10:00 UTC'), findsOneWidget);
    expect(find.text('What happens next'), findsOneWidget);
    expect(find.byType(TextFormField), findsNothing,
        reason: 'a second submission is not offered');
    expect(tester.takeException(), isNull);
  });

  testWidgets('a failed send keeps the statement and explains', (tester) async {
    final g = gateway(status: 503);
    await pump(
        tester,
        ScriptedStanding()..noticeValue = videoNotice(appealable: true),
        g.repo);
    await tester.enterText(
        find.byType(TextFormField), 'The audio is licensed to me.');
    await tester.tap(find.text('Send review request'));
    await settleAsync(tester);
    expect(find.byKey(const ValueKey('appeal-failure')), findsOneWidget);
    expect(find.text('We couldn’t send your request'), findsOneWidget);
    expect(find.textContaining('Your statement is kept'), findsOneWidget);
    expect(find.text('The audio is licensed to me.'), findsOneWidget);
    expect(find.text('Try again'), findsOneWidget);
    expect(find.byKey(const ValueKey('appeal-receipt')), findsNothing);
  });

  testWidgets('403 and 409 are explained and never show a receipt',
      (tester) async {
    for (final (status, text) in [
      (403, 'A review request is not available for this decision.'),
      (409, 'A review request already exists for this decision.'),
    ]) {
      final g = gateway(status: status);
      await pump(
          tester,
          ScriptedStanding()..noticeValue = videoNotice(appealable: true),
          g.repo);
      await tester.enterText(
          find.byType(TextFormField), 'The audio is licensed to me.');
      await tester.tap(find.text('Send review request'));
      await settleAsync(tester);
      expect(find.text(text), findsOneWidget, reason: '$status');
      expect(find.byKey(const ValueKey('appeal-receipt')), findsNothing);
    }
  });

  testWidgets('while sending the form is locked and cannot be submitted twice',
      (tester) async {
    final gate = Completer<void>();
    final requests = <http.Request>[];
    final fixture = AccountFixture(handler: (request) async {
      requests.add(request);
      if (request.url.path.endsWith('/appeals')) {
        await gate.future;
        return jsonResponse({
          'id': '00000000-0000-4000-8000-000000000a01',
          'video_id': videoId,
          'status': 'open',
          'created_at': '2026-11-20T10:00:00Z',
        }, 201);
      }
      return jsonResponse({});
    });
    await pump(
        tester,
        ScriptedStanding()..noticeValue = videoNotice(appealable: true),
        LiveModerationRepository(fixture.account));
    await tester.enterText(
        find.byType(TextFormField), 'The audio is licensed to me.');
    await tester.tap(find.text('Send review request'));
    await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 100)));
    await tester.pump();
    expect(find.text('Sending…'), findsOneWidget);
    final button = tester.widget<FilledButton>(find.byType(FilledButton));
    expect(button.onPressed, isNull);
    await tester.tap(find.text('Sending…'), warnIfMissed: false);
    await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 100)));
    await tester.pump();
    expect(requests.where((r) => r.url.path.endsWith('/appeals')).length, 1);
    gate.complete();
    await settleAsync(tester);
    expect(find.byKey(const ValueKey('appeal-receipt')), findsOneWidget);
  });

  testWidgets('validation is shown without sending and the statement is kept',
      (tester) async {
    final g = gateway();
    await pump(
        tester,
        ScriptedStanding()..noticeValue = videoNotice(appealable: true),
        g.repo);
    expect(find.text('Ask for a review.'), findsOneWidget);
    expect(find.text('This decision can be reviewed'), findsOneWidget);
    await tester.enterText(find.byType(TextFormField), 'Not fair');
    await tester.tap(find.text('Send review request'));
    await settleAsync(tester);
    expect(find.text('Write at least 10 characters.'), findsOneWidget);
    expect(find.text('Not fair'), findsOneWidget);
    expect(g.requests.where((r) => r.url.path.endsWith('/appeals')), isEmpty);
  });

  testWidgets('an ineligible or already-appealed notice never reaches the endpoint',
      (tester) async {
    for (final notice in [
      videoNotice(),
      videoNotice(appealable: true, appeal: ownAppeal()),
    ]) {
      final g = gateway();
      await pump(tester, ScriptedStanding()..noticeValue = notice, g.repo);
      expect(find.byType(TextFormField), findsNothing);
      expect(find.text('Send review request'), findsNothing);
      expect(find.text('Ask for a review.'), findsNothing);
      expect(g.requests.where((r) => r.url.path.endsWith('/appeals')), isEmpty);
    }
  });

  testWidgets('an existing request is shown and cannot be sent again',
      (tester) async {
    final g = gateway();
    await pump(
        tester,
        ScriptedStanding()
          ..noticeValue = videoNotice(appealable: true, appeal: ownAppeal()),
        g.repo);
    expect(find.text('Your review request'), findsOneWidget);
    expect(find.text('Send review request'), findsNothing);
  });

  testWidgets('the notice leads to the appeal screen only when eligible',
      (tester) async {
    useViewport(tester, AuditViewport.standard);
    Future<void> notice(bool eligible) async {
      pushed.clear();
      await tester.pumpWidget(host(LiveNoticeScreen(
          route: const ScreenRoute(76, entityId: videoId),
          catalog: catalog,
          repository: ScriptedStanding()
            ..noticeValue = videoNotice(appealable: eligible))));
      await settleAsync(tester);
    }

    await notice(false);
    expect(find.text('Request a review'), findsNothing);
    await notice(true);
    await tester.scrollUntilVisible(find.text('Request a review'), 200,
        scrollable: find.byType(Scrollable).first);
    await tester.ensureVisible(find.text('Request a review'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Request a review'));
    await settleAsync(tester);
    expect(pushed.last.name, '/mobile/M-078');
    expect((pushed.last.arguments as ScreenRoute).entityId, videoId);
  });

  testWidgets('layout holds at 2x text on a small iPhone', (tester) async {
    final g = gateway();
    useViewport(tester, AuditViewport.small, textScale: 2);
    await tester.pumpWidget(host(LiveAppealScreen(
        route: const ScreenRoute(78, entityId: videoId),
        catalog: catalog,
        standing: ScriptedStanding()
          ..noticeValue = videoNotice(appealable: true),
        moderation: g.repo)));
    await settleAsync(tester);
    expect(tester.takeException(), isNull);
  });
}
