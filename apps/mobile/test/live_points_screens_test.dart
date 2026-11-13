import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/app/screen_route.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/features/points/live_points_repository.dart';
import 'package:kolovibe/features/points/live_points_screen.dart';

import 'support/points_fakes.dart';
import 'support/upload_fakes.dart';

/// Widget tests with a scripted (fake) points service and the real design
/// catalog. No HTTP, platform channels or device APIs are exercised.
void main() {
  late DesignCatalog catalog;
  late ScriptedPoints service;
  late List<RouteSettings> pushed;

  setUpAll(() async => catalog = await DesignCatalog.load());
  setUp(() {
    service = ScriptedPoints();
    pushed = [];
  });

  Future<void> pump(WidgetTester tester, int screen,
      {String? entityId,
      double textScale = 1,
      Future<String?> Function(String)? titles}) async {
    await tester.pumpWidget(const SizedBox());
    await tester.pumpWidget(MaterialApp(
      builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context)
              .copyWith(textScaler: TextScaler.linear(textScale)),
          child: child!),
      home: LivePointsScreen(
          route: ScreenRoute(screen, entityId: entityId),
          catalog: catalog,
          repository: service,
          videoTitle: titles),
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

  Future<void> reveal(WidgetTester tester, Finder finder) async {
    await tester.scrollUntilVisible(finder, 120,
        scrollable: find.byType(Scrollable).first);
    await tester.pumpAndSettle();
  }

  Future<void> tapText(WidgetTester tester, String text) async {
    final finder = find.text(text);
    await reveal(tester, finder);
    await tester.tap(finder);
    await tester.pumpAndSettle();
  }

  List<PointsEntry> mixedLedger() => [
        ledgerEntry(1, amount: 120, video: videoId),
        ledgerEntry(2, status: 'pending', amount: 160),
        ledgerEntry(3, status: 'withheld', amount: 40),
        ledgerEntry(4, status: 'adjustments', amount: -20),
      ];

  group('M-061 Lone Stars overview', () {
    testWidgets('shows loading first', (tester) async {
      service.ledger = mixedLedger();
      await tester.pumpWidget(MaterialApp(
          home: LivePointsScreen(
              route: const ScreenRoute(61),
              catalog: catalog,
              repository: service)));
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      await tester.pumpAndSettle();
    });

    testWidgets('shows only the totals the server returned', (tester) async {
      service
        ..current = serverBalance(
            balance: 1240, pending: 161, withheld: 42, reversed: 20)
        ..ledger = mixedLedger();
      await pump(tester, 61);
      expect(find.text('1,240'), findsOneWidget);
      expect(find.text('Confirmed Lone Stars'), findsOneWidget);
      expect(find.text('Non-cash recognition. Not money or redeemable value.'),
          findsOneWidget);
      expect(find.widgetWithText(ListTile, 'Pending'), findsOneWidget);
      expect(find.text('161'), findsOneWidget);
      expect(find.text('42'), findsOneWidget);
      expect(find.text('Recent recognition'), findsOneWidget);
      expect(find.text('Qualified engagement'), findsOneWidget);
      expect(find.text('Activity being checked'), findsOneWidget);
    });

    testWidgets('tiles and links lead to the detail screens', (tester) async {
      service.ledger = mixedLedger();
      await pump(tester, 61);
      for (final (label, screen) in [
        ('Pending', 63),
        ('Withheld', 66),
        ('Reversed', 67),
        ('History', 64),
        ('How recognition works', 68),
      ]) {
        pushed.clear();
        await tapText(tester, label);
        expect(lastRoute().screen, screen, reason: label);
        await pump(tester, 61);
      }
    });

    testWidgets('opening a row passes its id, never an amount', (tester) async {
      service.ledger = mixedLedger();
      await pump(tester, 61);
      await tapText(tester, 'Excluded activity');
      expect(lastRoute().screen, 65);
      expect(lastRoute().entityId, entryId(3));
    });

    testWidgets('exposes no way to award, redeem or withdraw', (tester) async {
      service.ledger = mixedLedger();
      for (final screen in [61, 62, 63, 64, 66, 67, 68]) {
        await pump(tester, screen);
        final buttons = find.byWidgetPredicate((w) =>
            w is ButtonStyleButton &&
            w.child is Text &&
            RegExp(r'redeem|withdraw|cash|claim|award|convert|spend',
                    caseSensitive: false)
                .hasMatch((w.child as Text).data ?? ''));
        expect(buttons, findsNothing, reason: 'M-0$screen');
        expect(find.byType(TextField), findsNothing, reason: 'M-0$screen');
      }
    });

    testWidgets('pull to refresh reads the server again', (tester) async {
      service.ledger = mixedLedger();
      await pump(tester, 61);
      expect(service.balanceReads, 1);
      service.current = serverBalance(balance: 1300);
      await tester.fling(
          find.byType(Scrollable).first, const Offset(0, 400), 1000);
      await tester.pumpAndSettle();
      expect(service.balanceReads, 2);
      expect(find.text('1,300'), findsOneWidget);
    });

    testWidgets('a failed refresh keeps the last data and says so',
        (tester) async {
      service.ledger = mixedLedger();
      await pump(tester, 61);
      service.balanceFailure = offlineFailure;
      await tester.fling(
          find.byType(Scrollable).first, const Offset(0, 400), 1000);
      await tester.pumpAndSettle();
      expect(find.text('Could not refresh'), findsOneWidget);
      expect(find.text('1,240'), findsOneWidget);
      service.balanceFailure = null;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Could not refresh'), findsNothing);
    });
  });

  group('M-069 No points activity', () {
    testWidgets('an empty ledger shows the empty state and no sample points',
        (tester) async {
      service
        ..current =
            serverBalance(balance: 0, pending: 0, withheld: 0, reversed: 0)
        ..ledger = [];
      await pump(tester, 69);
      expect(find.text('No points activity'), findsOneWidget);
      expect(find.text('Your story starts here.'), findsOneWidget);
      expect(find.text('No Lone Stars activity yet'), findsOneWidget);
      expect(find.textContaining('Activity does not guarantee an award'),
          findsOneWidget);
      expect(find.text('1,240'), findsNothing);
      expect(find.text('Recent recognition'), findsNothing);
      await tapText(tester, 'Visit Creator Studio');
      expect(lastRoute().screen, 37);
    });

    testWidgets('the overview falls back to this state when there is none',
        (tester) async {
      service
        ..current =
            serverBalance(balance: 0, pending: 0, withheld: 0, reversed: 0)
        ..ledger = [];
      await pump(tester, 61);
      expect(find.text('Your story starts here.'), findsOneWidget);
      await tapText(tester, 'How Lone Stars work');
      expect(lastRoute().screen, 68);
    });

    testWidgets('M-069 with real activity shows the ledger instead',
        (tester) async {
      service.ledger = mixedLedger();
      await pump(tester, 69);
      expect(find.text('Your story starts here.'), findsNothing);
      expect(find.text('1,240'), findsOneWidget);
    });
  });

  group('load failures', () {
    testWidgets('offline shows retry, and retry recovers', (tester) async {
      service
        ..balanceFailure = offlineFailure
        ..ledger = mixedLedger();
      await pump(tester, 61);
      expect(find.text('You are offline'), findsOneWidget);
      service.balanceFailure = null;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('1,240'), findsOneWidget);
    });

    testWidgets('an expired session offers sign-in and returns here',
        (tester) async {
      service.balanceFailure = expiredFailure;
      await pump(tester, 64);
      expect(find.text('Session expired'), findsOneWidget);
      await tester.tap(find.text('Sign in'));
      await tester.pumpAndSettle();
      expect(lastRoute().screen, 4);
      expect(lastRoute().returnTo, 64);
    });

    testWidgets(
        'an account that is not an approved creator is told how to '
        'proceed', (tester) async {
      service.balanceFailure = notCreator;
      await pump(tester, 61);
      expect(find.text('Lone Stars are for approved creators'), findsOneWidget);
      expect(find.text('1,240'), findsNothing);
      await tester.tap(find.text('Open Creator Studio'));
      await tester.pumpAndSettle();
      expect(lastRoute().screen, 37);
    });

    testWidgets('an unreadable response shows an error, not partial data',
        (tester) async {
      service
        ..ledger = mixedLedger()
        ..entryFailure = const FormatException('bad');
      await pump(tester, 61);
      expect(find.text('Something went wrong'), findsOneWidget);
      expect(find.textContaining('could not be read'), findsOneWidget);
      expect(find.text('1,240'), findsNothing);
    });
  });

  group('M-062 Confirmed and M-063 Pending', () {
    testWidgets('M-062 lists only confirmed rows from the server filter',
        (tester) async {
      service.ledger = mixedLedger();
      await pump(tester, 62);
      expect(service.entryReads.single.filter, PointsFilter.confirmed);
      expect(find.text('Confirmed Lone Stars'), findsWidgets);
      expect(find.text('Qualified engagement'), findsOneWidget);
      expect(find.text('Activity being checked'), findsNothing);
      await tapText(tester, 'View points history');
      expect(lastRoute().screen, 64);
    });

    testWidgets('M-063 shows the pending total and never promises timing',
        (tester) async {
      service
        ..current = serverBalance(pending: 160)
        ..ledger = mixedLedger();
      await pump(tester, 63);
      expect(service.entryReads.single.filter, PointsFilter.pending);
      expect(find.text('160'), findsWidgets);
      expect(find.text('Pending Lone Stars'), findsWidgets);
      expect(find.textContaining('No processing time is promised'),
          findsOneWidget);
      expect(find.textContaining('not guaranteed'), findsOneWidget);
      expect(find.text('Excluded activity'), findsNothing);
      await tapText(tester, 'Read eligibility rules');
      expect(lastRoute().screen, 68);
    });

    testWidgets('an empty pending list says nothing is being checked',
        (tester) async {
      service.ledger = [ledgerEntry(1)];
      await pump(tester, 63);
      expect(find.text('Nothing is being checked right now.'), findsOneWidget);
    });
  });

  group('M-064 Transaction history', () {
    testWidgets('filters ask the server, and withheld rows are in All',
        (tester) async {
      service.ledger = mixedLedger();
      await pump(tester, 64);
      expect(find.text('Excluded activity'), findsOneWidget);
      expect(find.text('Recognition adjustment'), findsOneWidget);
      for (final (label, filter, shown) in [
        ('Confirmed', PointsFilter.confirmed, 'Qualified engagement'),
        ('Pending', PointsFilter.pending, 'Activity being checked'),
        ('Adjustments', PointsFilter.adjustments, 'Recognition adjustment'),
        ('All', PointsFilter.all, 'Excluded activity'),
      ]) {
        await tester.tap(find.widgetWithText(ChoiceChip, label));
        await tester.pumpAndSettle();
        expect(service.entryReads.last.filter, filter, reason: label);
        expect(service.entryReads.last.cursor, isNull);
        expect(find.text(shown), findsOneWidget, reason: label);
      }
      expect(find.text('Recognition activity, not financial transactions.'),
          findsOneWidget);
    });

    testWidgets('signed amounts use the server value and a real minus',
        (tester) async {
      service.ledger = mixedLedger();
      await pump(tester, 64);
      expect(find.text('+120'), findsOneWidget);
      expect(find.text('+160'), findsOneWidget);
      expect(find.text('40'), findsOneWidget);
      expect(find.text('−20'), findsOneWidget);
    });

    testWidgets('pages with Load more, and the end has no button',
        (tester) async {
      service = ScriptedPoints(pageSize: 3)
        ..ledger = [for (var n = 1; n <= 5; n++) ledgerEntry(n)];
      await pump(tester, 64);
      expect(find.text('Qualified engagement'), findsNWidgets(3));
      await tapText(tester, 'Load more');
      expect(find.text('Qualified engagement'), findsNWidgets(5));
      expect(find.text('Load more'), findsNothing);
      expect(service.entryReads.last.cursor, entryId(3));
    });

    testWidgets('a failed page keeps the rows and retries in place',
        (tester) async {
      service = ScriptedPoints(pageSize: 3)
        ..ledger = [for (var n = 1; n <= 5; n++) ledgerEntry(n)];
      await pump(tester, 64);
      service.entryFailures.add(offlineFailure);
      await tapText(tester, 'Load more');
      expect(find.text('Could not load more activity'), findsOneWidget);
      expect(find.text('Qualified engagement'), findsNWidgets(3));
      await tapText(tester, 'Try again');
      expect(find.text('Could not load more activity'), findsNothing);
      expect(find.text('Qualified engagement'), findsNWidgets(5));
    });

    testWidgets('an empty filter says so', (tester) async {
      service.ledger = [ledgerEntry(1)];
      await pump(tester, 64);
      await tester.tap(find.widgetWithText(ChoiceChip, 'Pending'));
      await tester.pumpAndSettle();
      expect(find.text('No activity for this filter yet.'), findsOneWidget);
    });
  });

  group('M-065 Transaction details', () {
    testWidgets('a confirmed entry shows source, date and status',
        (tester) async {
      service.ledger = mixedLedger();
      await pump(tester, 65,
          entityId: entryId(1),
          titles: (id) async => id == videoId ? 'Waterside at dawn' : null);
      expect(find.text('+120 Lone Stars'), findsOneWidget);
      expect(find.text('Confirmed · Qualified engagement'), findsOneWidget);
      expect(find.text('Waterside at dawn'), findsOneWidget);
      expect(find.text('Qualification checks completed'), findsOneWidget);
      expect(find.textContaining('no cash value, exchange rate or withdrawal'),
          findsOneWidget);
      expect(service.detailReads, [entryId(1)]);
    });

    testWidgets('an unknown source title is stated, not invented',
        (tester) async {
      service.ledger = mixedLedger();
      await pump(tester, 65,
          entityId: entryId(1),
          titles: (_) async => throw const ApiFailure(404, 'gone'));
      expect(find.text('Video details are unavailable'), findsOneWidget);
    });

    testWidgets('an entry with no video has no source row', (tester) async {
      service.ledger = mixedLedger();
      await pump(tester, 65, entityId: entryId(2));
      expect(find.text('Source'), findsNothing);
      expect(find.text('This activity is still being checked'), findsOneWidget);
    });

    testWidgets('a withheld entry explains the limits of what is shown',
        (tester) async {
      service.ledger = mixedLedger();
      await pump(tester, 65, entityId: entryId(3));
      expect(find.text('40 Lone Stars'), findsOneWidget);
      expect(find.textContaining('Details are limited'), findsOneWidget);
      await tapText(tester, 'Review withheld points');
      expect(lastRoute().screen, 66);
    });

    testWidgets('a reversal says it is not a financial penalty',
        (tester) async {
      service.ledger = mixedLedger();
      await pump(tester, 65, entityId: entryId(4));
      expect(find.text('−20 Lone Stars'), findsOneWidget);
      expect(find.textContaining('not a payment, charge or financial penalty'),
          findsOneWidget);
      await tapText(tester, 'View reversed points');
      expect(lastRoute().screen, 67);
    });

    testWidgets('someone else\'s or a missing entry is "not found"',
        (tester) async {
      service.ledger = mixedLedger();
      await pump(tester, 65, entityId: entryId(99));
      expect(find.text('Not found'), findsOneWidget);
      expect(find.textContaining('+'), findsNothing);
    });

    testWidgets('no entity id asks the user to choose an entry',
        (tester) async {
      await pump(tester, 65);
      expect(find.text('Choose an entry'), findsOneWidget);
      expect(service.detailReads, isEmpty);
      await tester.tap(find.text('View points history'));
      await tester.pumpAndSettle();
      expect(lastRoute().screen, 64);
    });

    testWidgets('offline offers retry that recovers', (tester) async {
      service
        ..ledger = mixedLedger()
        ..entryFailure = offlineFailure;
      await pump(tester, 65, entityId: entryId(1));
      expect(find.text('You are offline'), findsOneWidget);
      service.entryFailure = null;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('+120 Lone Stars'), findsOneWidget);
    });

    testWidgets('Back to history returns to the list', (tester) async {
      service.ledger = mixedLedger();
      await pump(tester, 65, entityId: entryId(1));
      await tapText(tester, 'Back to history');
      expect(lastRoute().screen, 64);
    });
  });

  group('M-066 Withheld and M-067 Reversed', () {
    testWidgets('M-066 shows the server total and only withheld rows',
        (tester) async {
      service
        ..current = serverBalance(withheld: 40)
        ..ledger = mixedLedger();
      await pump(tester, 66);
      expect(find.text('40 withheld'), findsOneWidget);
      expect(find.text('Excluded activity'), findsOneWidget);
      expect(find.text('Qualified engagement'), findsNothing);
      expect(find.textContaining('not a money deduction'), findsOneWidget);
      await tapText(tester, 'Review eligibility rules');
      expect(lastRoute().screen, 68);
    });

    testWidgets('M-066 keeps looking through older activity on request',
        (tester) async {
      service = ScriptedPoints(pageSize: 1)
        ..ledger = [
          for (var n = 1; n <= 9; n++) ledgerEntry(n),
          ledgerEntry(10, status: 'withheld'),
        ];
      await pump(tester, 66);
      expect(find.text('Excluded activity'), findsNothing);
      await tapText(tester, 'Check older activity');
      expect(find.text('Excluded activity'), findsOneWidget);
    });

    testWidgets('M-066 with nothing withheld says so', (tester) async {
      service
        ..current = serverBalance(withheld: 0)
        ..ledger = [ledgerEntry(1)];
      await pump(tester, 66);
      expect(find.text('0 withheld'), findsOneWidget);
      expect(find.text('No withheld activity found.'), findsOneWidget);
    });

    testWidgets('M-067 lists adjustments with the server reversed total',
        (tester) async {
      service
        ..current = serverBalance(reversed: 20)
        ..ledger = mixedLedger();
      await pump(tester, 67);
      expect(service.entryReads.single.filter, PointsFilter.adjustments);
      expect(find.text('20 reversed'), findsOneWidget);
      expect(find.text('Recognition adjustment'), findsOneWidget);
      expect(find.textContaining('not a payment, charge or financial penalty'),
          findsOneWidget);
      await tapText(tester, 'View related history');
      expect(lastRoute().screen, 64);
    });
  });

  group('M-068 Engagement eligibility', () {
    testWidgets('is static guidance and calls no service', (tester) async {
      await pump(tester, 68);
      expect(find.text('Real connection. Real recognition.'), findsOneWidget);
      expect(find.text('Not a rewards currency'), findsOneWidget);
      expect(find.textContaining('No cash value'), findsOneWidget);
      expect(service.balanceReads, 0);
      expect(service.entryReads, isEmpty);
      await tapText(tester, 'Back to Lone Stars');
      expect(lastRoute().screen, 61);
    });
  });

  group('accessibility and layout', () {
    testWidgets('every screen fits at 2.0 text scale', (tester) async {
      service.ledger = mixedLedger();
      for (final screen in [61, 62, 63, 64, 66, 67, 68, 69]) {
        await pump(tester, screen, textScale: 2);
        expect(tester.takeException(), isNull, reason: 'M-0$screen');
      }
      await pump(tester, 65, entityId: entryId(1), textScale: 2);
      expect(tester.takeException(), isNull);
    });

    testWidgets('rows read out title, state, date and amount', (tester) async {
      service.ledger = mixedLedger();
      await pump(tester, 64);
      final handle = tester.ensureSemantics();
      expect(
          find.bySemanticsLabel(
              RegExp(r'Excluded activity, Withheld, .*, 40 Lone Stars')),
          findsOneWidget);
      handle.dispose();
    });
  });
}
