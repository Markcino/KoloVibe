import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/core/presentation/feature_repository.dart';
import 'package:kolovibe/features/discovery/discovery_catalog_screen.dart';
import 'package:kolovibe/features/discovery/live_video_repository.dart';
import 'package:kolovibe/features/discovery/search_history.dart';
import 'fl_a_support.dart';

const alice = '00000000-0000-4000-8000-0000000000a1';
const bob = '00000000-0000-4000-8000-0000000000b2';

class BrokenStore implements SearchHistoryStore {
  @override
  Future<String?> read() async => throw StateError('keychain unavailable');
  @override
  Future<void> write(String value) async => throw StateError('no');
  @override
  Future<void> delete() async => throw StateError('no');
}

void main() {
  late DateTime now;
  late MemorySearchHistoryStore store;
  late SearchHistory history;
  setUp(() {
    now = DateTime.utc(2026, 11, 20, 12);
    store = MemorySearchHistoryStore();
    history = SearchHistory(store, clock: () => now);
  });

  group('rules', () {
    test('keeps at most eight, newest first', () async {
      for (var i = 1; i <= 10; i++) {
        now = now.add(const Duration(minutes: 1));
        await history.add(alice, 'term $i');
      }
      final list = await history.recent(alice);
      expect(list.length, 8);
      expect(list.first, 'term 10');
      expect(list.last, 'term 3');
    });

    test('searching again moves a phrase to the top without a copy', () async {
      await history.add(alice, 'River Songs');
      now = now.add(const Duration(minutes: 1));
      await history.add(alice, 'comedy');
      now = now.add(const Duration(minutes: 1));
      await history.add(alice, '  river   songs ');
      expect(await history.recent(alice), ['river   songs', 'comedy']);
    });

    test('an entry expires fourteen days after it was last searched', () async {
      await history.add(alice, 'old');
      now = now.add(const Duration(days: 13, hours: 23, minutes: 59));
      expect(await history.recent(alice), ['old']);
      now = now.add(const Duration(minutes: 1));
      expect(await history.recent(alice), isEmpty);
      expect(store.value, isNull, reason: 'expired data is deleted, not hidden');
    });

    test('searching again renews the retention clock', () async {
      await history.add(alice, 'again');
      now = now.add(const Duration(days: 10));
      await history.add(alice, 'again');
      now = now.add(const Duration(days: 10));
      expect(await history.recent(alice), ['again']);
    });

    test('rejects blank, over-long and control-character text', () async {
      for (final bad in ['', '   ', 'x' * 101, 'tab\there', 'new\nline', 'nul\u0000', 'del\u007f']) {
        await history.add(alice, bad);
      }
      expect(await history.recent(alice), isEmpty);
      await history.add(alice, 'x' * 100);
      expect((await history.recent(alice)).single.length, 100);
    });

    test('remove and clear delete immediately', () async {
      await history.add(alice, 'one');
      await history.add(alice, 'two');
      await history.remove(alice, 'ONE');
      expect(await history.recent(alice), ['two']);
      await history.clear(alice);
      expect(await history.recent(alice), isEmpty);
      expect(store.value, isNull);
    });
  });

  group('accounts', () {
    test('one account never sees another account\'s searches', () async {
      await history.add(alice, 'alice private');
      await history.add(bob, 'bob private');
      expect(await history.recent(alice), ['alice private']);
      expect(await history.recent(bob), ['bob private']);
      await history.clear(alice);
      expect(await history.recent(alice), isEmpty);
      expect(await history.recent(bob), ['bob private']);
    });

    test('a signed-out or invalid account has no list and stores nothing',
        () async {
      await history.add(null, 'secret');
      await history.add('not-an-id', 'secret');
      expect(await history.recent(null), isEmpty);
      expect(await history.recent('not-an-id'), isEmpty);
      expect(store.value, isNull);
    });

    test('clearAll leaves nothing of any account', () async {
      await history.add(alice, 'a');
      await history.add(bob, 'b');
      await history.clearAll();
      expect(store.value, isNull);
      expect(await history.recent(alice), isEmpty);
      expect(await history.recent(bob), isEmpty);
    });
  });

  group('resilience', () {
    test('an unavailable store means no history and never throws', () async {
      final broken = SearchHistory(BrokenStore(), clock: () => now);
      await broken.add(alice, 'x');
      expect(await broken.recent(alice), isEmpty);
      await broken.remove(alice, 'x');
      await broken.clear(alice);
      await broken.clearAll();
    });

    test('corrupt, tampered or future-dated data is ignored', () async {
      store.value = 'not json';
      expect(await history.recent(alice), isEmpty);
      store.value = jsonEncode({'v': 2, 'accounts': {}});
      expect(await history.recent(alice), isEmpty);
      store.value = jsonEncode({
        'v': 1,
        'accounts': {
          alice: [
            {'t': 'fine', 'at': now.millisecondsSinceEpoch},
            {'t': 'future', 'at': now.add(const Duration(days: 30)).millisecondsSinceEpoch},
            {'t': 5, 'at': 1},
            {'t': 'bad\u0000', 'at': now.millisecondsSinceEpoch},
            'nonsense',
          ],
          'not-an-id': [
            {'t': 'orphan', 'at': now.millisecondsSinceEpoch}
          ],
        }
      });
      expect(await history.recent(alice), ['fine']);
      expect(store.value!.contains('orphan'), isFalse);
    });

    test('overlapping calls do not lose writes', () async {
      await Future.wait([for (var i = 0; i < 6; i++) history.add(alice, 'q$i')]);
      expect((await history.recent(alice)).toSet(), {for (var i = 0; i < 6; i++) 'q$i'});
    });
  });

  group('sign-out', () {
    Future<(AccountFixture, SearchHistory, MemorySearchHistoryStore)> signedIn(
        {int logoutStatus = 204}) async {
      final fixture = AccountFixture(handler: (request) async {
        if (request.url.path.endsWith('/auth/login')) {
          return jsonResponse({
            'access_token': 'access',
            'refresh_token': 'refresh',
            'user': accountData,
          });
        }
        if (request.url.path.endsWith('/auth/logout')) {
          return jsonResponse({}, logoutStatus);
        }
        return jsonResponse({});
      });
      final local = MemorySearchHistoryStore();
      final h = SearchHistory(local);
      fixture.account.onSessionEnded = h.clearAll;
      await fixture.account.executeChecked(UiRequest(UiOperation.signIn,
          fields: {'Email address': 'mark@example.test', 'Password': 'x' * 14}));
      return (fixture, h, local);
    }

    test('the account id comes from the session and ends with it', () async {
      final (fixture, _, _) = await signedIn();
      expect(fixture.account.signedInAccountId, accountId);
      await fixture.account.signOut();
      expect(fixture.account.signedInAccountId, isNull);
    });

    test('signing out deletes the list', () async {
      final (fixture, h, local) = await signedIn();
      await h.add(fixture.account.signedInAccountId, 'private');
      expect(local.value, isNotNull);
      await fixture.account.signOut();
      expect(local.value, isNull);
    });

    test('signing out deletes the list even when the server cannot confirm',
        () async {
      final (fixture, h, local) = await signedIn(logoutStatus: 503);
      await h.add(fixture.account.signedInAccountId, 'private');
      await expectLater(fixture.account.signOut(), throwsA(isA<ApiFailure>()));
      expect(local.value, isNull);
      expect(fixture.account.signedInAccountId, isNull);
    });

    test('a failing history store cannot block sign-out', () async {
      final (fixture, _, _) = await signedIn();
      fixture.account.onSessionEnded = () async => throw StateError('boom');
      await fixture.account.signOut();
      expect(fixture.store.value, isNull);
    });

    test('nothing is sent to the service when searches are saved or cleared',
        () async {
      final (fixture, h, _) = await signedIn();
      final before = fixture.requests.length;
      await h.add(fixture.account.signedInAccountId, 'private');
      await h.recent(fixture.account.signedInAccountId);
      await h.clear(fixture.account.signedInAccountId);
      expect(fixture.requests.length, before);
    });
  });

  group('M-021', () {
    late DesignCatalog catalog;
    setUpAll(() async => catalog = await DesignCatalog.load());
    final calls = <Map<String, String?>>[];

    Future<void> settle(WidgetTester tester) async {
      for (var i = 0; i < 6; i++) {
        await tester.runAsync(
            () => Future<void>.delayed(const Duration(milliseconds: 2)));
        await tester.pump(const Duration(milliseconds: 50));
      }
      await tester.pumpAndSettle();
    }

    Future<(SearchHistory, AccountFixture)> open(
        WidgetTester tester, MemorySearchHistoryStore local,
        {bool signedInUser = true, List<String> seed = const []}) async {
      calls.clear();
      final fixture = AccountFixture(handler: (request) async {
        if (request.url.path.endsWith('/auth/login')) {
          return jsonResponse({
            'access_token': 'access',
            'refresh_token': 'refresh',
            'user': accountData,
          });
        }
        return jsonResponse({});
      });
      final h = SearchHistory(local);
      if (signedInUser) {
        await tester.runAsync(() => fixture.account.executeChecked(UiRequest(
            UiOperation.signIn,
            fields: {'Email address': 'm@example.test', 'Password': 'x' * 14})));
        for (final term in seed.reversed) {
          await tester.runAsync(() => h.add(fixture.account.signedInAccountId, term));
        }
      }
      final repo = _Catalog((q) {
        calls.add(q);
        return const LiveVideoPage([], null);
      });
      await tester.pumpWidget(MaterialApp(
          home: DiscoveryCatalogScreen(
              screen: 21,
              repository: repo,
              catalog: catalog,
              account: fixture.account,
              history: h)));
      await settle(tester);
      return (h, fixture);
    }

    testWidgets('shows the list, the privacy line and a Clear action',
        (tester) async {
      final local = MemorySearchHistoryStore();
      await open(tester, local, seed: ['hipco nights', 'monrovia']);
      expect(find.text('Recent searches'), findsOneWidget);
      expect(find.text('hipco nights'), findsOneWidget);
      expect(find.text('Clear'), findsOneWidget);
      expect(find.text('Saved on this phone for 14 days. Not sent to KoloVibe.'),
          findsOneWidget);
    });

    testWidgets('Clear deletes everything at once', (tester) async {
      final local = MemorySearchHistoryStore();
      await open(tester, local, seed: ['one', 'two']);
      await tester.tap(find.text('Clear'));
      await settle(tester);
      expect(find.text('Recent searches'), findsNothing);
      expect(find.text('one'), findsNothing);
      expect(local.value, isNull);
    });

    testWidgets('each entry can be removed', (tester) async {
      final local = MemorySearchHistoryStore();
      await open(tester, local, seed: ['one', 'two']);
      await tester.tap(find.byTooltip('Remove one from recent searches'));
      await settle(tester);
      expect(find.text('one'), findsNothing);
      expect(find.text('two'), findsOneWidget);
    });

    testWidgets('a signed-out person sees no list and nothing is stored',
        (tester) async {
      final local = MemorySearchHistoryStore();
      await open(tester, local, signedInUser: false);
      expect(find.text('Recent searches'), findsNothing);
      await tester.enterText(find.byType(TextField), 'secret');
      await tester.testTextInput.receiveAction(TextInputAction.search);
      await settle(tester);
      expect(local.value, isNull);
    });

    testWidgets('submitting a search saves it',
        (tester) async {
      final local = MemorySearchHistoryStore();
      final (h, fixture) = await open(tester, local);
      await tester.enterText(find.byType(TextField), 'river songs');
      await tester.testTextInput.receiveAction(TextInputAction.search);
      await settle(tester);
      expect(await tester.runAsync(() => h.recent(fixture.account.signedInAccountId)),
          ['river songs']);
      expect(calls.any((c) => c['q'] == 'river songs'), isTrue);
      expect(local.value!.contains('river songs'), isTrue);
    });

    testWidgets('tapping an entry runs that search', (tester) async {
      final local = MemorySearchHistoryStore();
      await open(tester, local, seed: ['monrovia nights']);
      await tester.tap(find.text('monrovia nights'));
      await settle(tester);
      expect(calls.any((c) => c['q'] == 'monrovia nights'), isTrue);
    });

    testWidgets('long recent searches and 2x text do not overflow',
        (tester) async {
      tester.view.physicalSize = const Size(375 * 2, 667 * 2);
      tester.view.devicePixelRatio = 2;
      addTearDown(tester.view.reset);
      final local = MemorySearchHistoryStore();
      await open(tester, local, seed: ['x' * 100, 'y' * 99]);
      expect(find.text('Recent searches'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });
}

class _Catalog extends LiveVideoRepository {
  _Catalog(this.onCall) : super(ApiClient('https://api.example.test/api/v1'));
  final LiveVideoPage Function(Map<String, String?>) onCall;
  @override
  Future<LiveVideoPage> filteredPage(
          {String? cursor,
          String? creatorId,
          String? query,
          String? category,
          String sort = 'recent'}) async =>
      onCall({'q': query, 'category': category, 'sort': sort});
}
