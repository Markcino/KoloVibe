import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/app/screen_route.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/core/security/credential_store.dart';
import 'package:kolovibe/features/account/live_account_repository.dart';
import 'package:kolovibe/features/content/live_content_repository.dart';
import 'package:kolovibe/features/content/live_content_screen.dart';

class _UnusedCredentials implements CredentialStore {
  @override
  Future<void> clearRefreshToken() async {}
  @override
  Future<String?> readRefreshToken() async => null;
  @override
  Future<void> writeRefreshToken(String token) async {}
}

class _ContentFixture extends LiveContentRepository {
  _ContentFixture()
      : super(LiveAccountRepository(
            ApiClient('https://api.example.test/api/v1'),
            _UnusedCredentials()));

  final videos = <OwnedVideo>[
    OwnedVideo(
      '00000000-0000-4000-8000-000000000001',
      '00000000-0000-4000-8000-000000000002',
      'My draft',
      '',
      'draft',
      DateTime.utc(2026, 11, 11),
    ),
  ];

  @override
  Future<OwnedVideoPage> library({String? cursor}) async =>
      OwnedVideoPage(List.of(videos), null);

  @override
  Future<void> deleteDraft(OwnedVideo video) async =>
      videos.removeWhere((item) => item.id == video.id);
}

void main() {
  late DesignCatalog catalog;
  setUpAll(() async => catalog = await DesignCatalog.load());

  testWidgets(
      'creator library confirms deletion and shows the real empty state',
      (tester) async {
    final repository = _ContentFixture();
    await tester.pumpWidget(MaterialApp(
      home: LiveContentScreen(
        route: const ScreenRoute(40),
        catalog: catalog,
        repository: repository,
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('My draft'), findsOneWidget);
    await tester.tap(find.byTooltip('Manage draft'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Delete draft'));
    await tester.pumpAndSettle();
    expect(find.text('Delete draft?'), findsOneWidget);
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(repository.videos, hasLength(1));
    await tester.tap(find.byTooltip('Manage draft'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Delete draft'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Delete'));
    await tester.pumpAndSettle();
    expect(repository.videos, isEmpty);
    expect(find.text('You have no videos yet.'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('rejected and removed videos link to their notice, others do not',
      (tester) async {
    final repository = _ContentFixture();
    OwnedVideo video(int n, String state) => OwnedVideo(
        '00000000-0000-4000-8000-00000000010$n',
        '00000000-0000-4000-8000-000000000002',
        'Video $state',
        '',
        state,
        DateTime.utc(2026, 11, 11));
    repository.videos
      ..clear()
      ..addAll([
        video(1, 'removed'),
        video(2, 'rejected'),
        video(3, 'published'),
      ]);
    final pushed = <RouteSettings>[];
    await tester.pumpWidget(MaterialApp(
      home: LiveContentScreen(
        route: const ScreenRoute(40),
        catalog: catalog,
        repository: repository,
      ),
      onGenerateRoute: (settings) {
        pushed.add(settings);
        return MaterialPageRoute<void>(
            settings: settings, builder: (_) => const Scaffold());
      },
    ));
    await tester.pumpAndSettle();
    expect(find.text('View notice'), findsNWidgets(2));
    await tester.tap(find.text('View notice').first);
    await tester.pumpAndSettle();
    final route = pushed.last.arguments as ScreenRoute;
    expect(route.screen, 76);
    expect(route.entityId, '00000000-0000-4000-8000-000000000101');
  });
}
