import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/features/moderation/live_restriction_repository.dart';
import 'package:kolovibe/features/moderation/live_standing_repository.dart';
import 'package:kolovibe/features/moderation/live_standing_screen.dart';

import 'support/standing_fakes.dart';
import 'support/upload_fakes.dart';

const measureId = '00000000-0000-4000-8000-000000000b01';
const creatorId = '00000000-0000-4000-8000-000000000c01';

Map<String, dynamic> measureJson(
        {String kind = 'upload',
        bool active = true,
        String? liftedAt,
        Object? appeal}) =>
    {
      'id': measureId,
      'kind': kind,
      'reason_code': 'SPAM_REPEAT',
      'policy_version': 'creator-enforcement-v1',
      'issued_at': '2026-11-25T12:00:00+00:00',
      'expires_at': null,
      'lifted_at': liftedAt,
      'active': active,
      'appeal': appeal,
    };

/// A scripted measures service. Mocked: no HTTP.
class ScriptedRestrictions extends LiveRestrictionRepository {
  ScriptedRestrictions() : super(unusedAccount());

  OwnMeasures value = OwnMeasures.fromJson({
    'creator_id': creatorId,
    'items': [measureJson()]
  });
  Object? readFailure, appealFailure;
  final appeals = <(String, String)>[];
  int reads = 0;

  @override
  Future<OwnMeasures> mine() async {
    reads++;
    final failure = readFailure;
    if (failure != null) throw failure;
    return value;
  }

  @override
  Future<MeasureAppeal> appeal(
      {required String measureId, required String reason}) async {
    appeals.add((measureId, reason.trim()));
    final failure = appealFailure;
    if (failure != null) throw failure;
    value = OwnMeasures.fromJson({
      'creator_id': creatorId,
      'items': [
        measureJson(appeal: {'id': measureId, 'status': 'open'})
      ]
    });
    return MeasureAppeal(measureId, 'open');
  }
}

void main() {
  group('parsing', () {
    test('accepts a measure and rejects private or inconsistent fields', () {
      final measures = OwnMeasures.fromJson({
        'creator_id': creatorId,
        'items': [measureJson()]
      });
      expect(measures.items.single.appealable, isTrue);
      expect(measures.items.single.kind, 'upload');
      for (final bad in [
        measureJson()..['reason'] = 'private',
        measureJson(kind: 'ban'),
        measureJson(liftedAt: '2026-11-25T13:00:00+00:00'),
        measureJson()..['issued_at'] = '2026-11-25T12:00:00',
        measureJson(appeal: {'id': measureId, 'status': 'pardoned'}),
      ]) {
        expect(
            () => OwnMeasures.fromJson({
                  'creator_id': creatorId,
                  'items': [bad]
                }),
            throwsFormatException);
      }
      expect(
          () => OwnMeasures.fromJson({
                'creator_id': null,
                'items': [measureJson()]
              }),
          throwsFormatException);
      expect(OwnMeasures.fromJson({'creator_id': null, 'items': []}).items,
          isEmpty);
    });

    test('a lifted or appealed measure is not appealable', () {
      final lifted = CreatorMeasure.fromJson(
          measureJson(active: false, liftedAt: '2026-11-25T13:00:00+00:00'));
      final appealed = CreatorMeasure.fromJson(
          measureJson(appeal: {'id': measureId, 'status': 'open'}));
      expect(lifted.appealable, isFalse);
      expect(appealed.appealable, isFalse);
    });

    test('an appeal needs a real statement before any request', () async {
      final repository = LiveRestrictionRepository(unusedAccount());
      expect(repository.appeal(measureId: measureId, reason: '  short  '),
          throwsFormatException);
      expect(
          repository.appeal(measureId: 'nope', reason: 'A long enough reason'),
          throwsFormatException);
    });
  });

  group('account status section', () {
    late DesignCatalog catalog;
    late ScriptedStanding standing;
    late ScriptedRestrictions restrictions;

    setUpAll(() async => catalog = await DesignCatalog.load());
    setUp(() {
      standing = ScriptedStanding();
      restrictions = ScriptedRestrictions();
    });

    Future<void> pump(WidgetTester tester) async {
      tester.view.physicalSize = const Size(1200, 3200);
      tester.view.devicePixelRatio = 2;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(MaterialApp(
          home: LiveStandingScreen(
              catalog: catalog,
              repository: standing,
              restrictions: restrictions),
          onGenerateRoute: (settings) => MaterialPageRoute<void>(
              settings: settings,
              builder: (_) => const Scaffold(body: Text('next screen')))));
      await tester.pumpAndSettle();
    }

    testWidgets('shows the measure and sends an appeal', (tester) async {
      await pump(tester);
      expect(find.text('Account measures'), findsOneWidget);
      expect(find.text('Uploads paused'), findsOneWidget);
      expect(find.textContaining('SPAM_REPEAT'), findsOneWidget);
      await tester.tap(find.text('Appeal this measure'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Send appeal'));
      await tester.pumpAndSettle();
      expect(find.text('Write at least 10 characters.'), findsOneWidget);
      expect(restrictions.appeals, isEmpty);
      await tester.enterText(
          find.byType(TextFormField), '  These were my own original videos ');
      await tester.tap(find.text('Send appeal'));
      await tester.pumpAndSettle();
      expect(restrictions.appeals,
          [(measureId, 'These were my own original videos')]);
      expect(find.text('Appeal under review'), findsOneWidget);
      expect(find.text('Appeal this measure'), findsNothing);
      expect(restrictions.reads, 2);
    });

    testWidgets('a refused appeal keeps the statement', (tester) async {
      restrictions.appealFailure = const ApiFailure(409, 'conflict');
      await pump(tester);
      await tester.tap(find.text('Appeal this measure'));
      await tester.pumpAndSettle();
      await tester.enterText(
          find.byType(TextFormField), 'These were my own original videos');
      await tester.tap(find.text('Send appeal'));
      await tester.pumpAndSettle();
      expect(find.textContaining('already has an appeal'), findsOneWidget);
      expect(find.text('These were my own original videos'), findsOneWidget);
    });

    testWidgets('a failed read leaves the rest of the status visible',
        (tester) async {
      restrictions.readFailure = const ApiFailure(404, 'Not found');
      await pump(tester);
      expect(find.text('Account measures are unavailable.'), findsOneWidget);
      expect(find.text('Content notices'), findsOneWidget);
      restrictions.readFailure = null;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Uploads paused'), findsOneWidget);
    });

    testWidgets('no section without a creator profile', (tester) async {
      standing.standingValue = const AccountStanding(null, false, []);
      await pump(tester);
      expect(find.text('Account measures'), findsNothing);
      expect(restrictions.reads, 0);
    });
  });
}
