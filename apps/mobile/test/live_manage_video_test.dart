import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kolovibe/app/screen_route.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/security/credential_store.dart';
import 'package:kolovibe/features/account/live_account_repository.dart';
import 'package:kolovibe/features/content/live_content_repository.dart';
import 'package:kolovibe/features/content/live_manage_video_screen.dart';
import 'package:kolovibe/features/content/manage_video_controller.dart';

class _Credentials implements CredentialStore {
  String? value = 'refresh';
  @override
  Future<void> clearRefreshToken() async => value = null;
  @override
  Future<String?> readRefreshToken() async => value;
  @override
  Future<void> writeRefreshToken(String token) async => value = token;
}

const _creator = '00000000-0000-4000-8000-000000000002';
const _video = '00000000-0000-4000-8000-000000000003';

Map<String, Object?> _json(
        {String state = 'published',
        String visibility = 'private',
        String title = 'My original',
        String description = 'A story',
        String? category = 'culture',
        List<String> tags = const [],
        Object? revision = 4,
        String? posterUrl}) =>
    {
      'id': _video,
      'creator_id': _creator,
      'title': title,
      'description': description,
      'category': category,
      'tags': tags,
      'cover_time_ms': null,
      'state': state,
      'visibility': visibility,
      'created_at': '2026-11-11T10:00:00Z',
      'published_at': state == 'published' ? '2026-11-12T10:00:00Z' : null,
      'poster_url': posterUrl,
      if (revision != null) 'revision': revision,
    };

class _Server {
  _Server(this.handler);
  final http.Response Function(http.Request request) handler;
  final calls = <String>[];

  LiveContentRepository repository() =>
      LiveContentRepository(LiveAccountRepository(
          ApiClient('https://api.example.test/api/v1',
              client: MockClient((request) async {
            if (request.url.path.endsWith('/auth/refresh')) {
              return http.Response(
                  jsonEncode(
                      {'access_token': 'access', 'refresh_token': 'rotated'}),
                  200);
            }
            expect(request.headers['Authorization'], 'Bearer access');
            calls.add('${request.method} ${request.url.path}');
            return handler(request);
          })),
          _Credentials()));
}

http.Response _ok(Object body, [int status = 200]) =>
    http.Response(jsonEncode(body), status,
        headers: {'content-type': 'application/json'});

/// A repository with no network: the screen tests drive the controller through its public contract.
class _Fake extends LiveContentRepository {
  _Fake(this.video, {this.onChange, this.failLoads = 0})
      : super(LiveAccountRepository(
            ApiClient('https://api.example.test/api/v1'), _Credentials()));

  OwnedVideo video;
  final ApiFailure? onChange;
  int failLoads;
  final calls = <String>[];

  @override
  Future<OwnedVideo> ownedVideo(String videoId) async {
    if (failLoads > 0) {
      failLoads--;
      throw const ApiFailure(503, 'x', offline: true);
    }
    return video;
  }

  @override
  Future<OwnedVideo> setVisibility(OwnedVideo v,
      {required bool publish}) async {
    calls.add(publish ? 'publish' : 'unpublish');
    if (onChange != null) throw onChange!;
    return video =
        OwnedVideo.fromJson(_json(visibility: publish ? 'public' : 'private'));
  }

  @override
  Future<OwnedVideo> editDetails(OwnedVideo v,
      {String? title,
      String? description,
      String? category,
      List<String>? tags,
      int? coverTimeMs}) async {
    calls.add('edit');
    return video;
  }

  @override
  Future<void> deleteVideo(OwnedVideo v) async => calls.add('delete');
}

void main() {
  group('repository', () {
    test('reads the owned detail including the moderation revision', () async {
      final server = _Server((_) => _ok(_json()));
      final video = await server.repository().ownedVideo(_video);
      expect(video.revision, 4);
      expect(server.calls, ['GET /api/v1/creators/me/videos/$_video']);
      expect(video.canPublish, isTrue);
      expect(video.canUnpublish, isFalse);
    });

    test('rejects a malformed or mismatched detail', () async {
      for (final body in [
        _json(revision: -1),
        _json(revision: 'x'),
        {..._json(), 'extra': 1},
        {..._json(), 'id': '00000000-0000-4000-8000-0000000000ff'},
      ]) {
        final server = _Server((_) => _ok(body));
        await expectLater(
            server.repository().ownedVideo(_video), throwsFormatException);
      }
      await expectLater(
          _Server((_) => _ok(_json())).repository().ownedVideo('nope'),
          throwsFormatException);
    });

    test('publish and unpublish post to the exact paths and check the result',
        () async {
      final server = _Server((request) => _ok(_json(
          visibility:
              request.url.path.endsWith('/publish') ? 'public' : 'private')));
      final repository = server.repository();
      final approved = OwnedVideo.fromJson(_json());
      final published = await repository.setVisibility(approved, publish: true);
      expect(published.isPublic, isTrue);
      final back = await repository.setVisibility(published, publish: false);
      expect(back.visibility, 'private');
      expect(server.calls, [
        'POST /api/v1/videos/$_video/publish',
        'POST /api/v1/videos/$_video/unpublish'
      ]);
    });

    test('never asks the server for an impossible change', () async {
      final server = _Server((_) => _ok(_json()));
      final repository = server.repository();
      for (final entry in {
        'review': true,
        'draft': true,
        'rejected': false,
        'removed': false,
      }.entries) {
        await expectLater(
            repository.setVisibility(
                OwnedVideo.fromJson(_json(state: entry.key)),
                publish: entry.value),
            throwsFormatException,
            reason: entry.key);
      }
      await expectLater(
          repository.setVisibility(OwnedVideo.fromJson(_json()),
              publish: false),
          throwsFormatException);
      await expectLater(
          repository.setVisibility(
              OwnedVideo.fromJson(_json(visibility: 'public')),
              publish: true),
          throwsFormatException);
      expect(server.calls, isEmpty);
    });

    test('a response that does not match the request is refused', () async {
      for (final body in [
        _json(visibility: 'private'),
        _json(state: 'review', visibility: 'public'),
        {
          ..._json(visibility: 'public'),
          'creator_id': '00000000-0000-4000-8000-0000000000aa'
        },
      ]) {
        final server = _Server((_) => _ok(body));
        await expectLater(
            server
                .repository()
                .setVisibility(OwnedVideo.fromJson(_json()), publish: true),
            throwsFormatException);
      }
    });

    test('review_required surfaces as a conflict with its code', () async {
      final server = _Server((_) =>
          _ok({'detail': 'Review required', 'code': 'review_required'}, 409));
      await expectLater(
          server
              .repository()
              .setVisibility(OwnedVideo.fromJson(_json()), publish: true),
          throwsA(isA<ApiFailure>()
              .having((f) => f.kind, 'kind', FailureKind.conflict)
              .having((f) => f.code, 'code', 'review_required')));
    });

    test('edit sends only changed fields and verifies the echo', () async {
      late Object? sent;
      final server = _Server((request) {
        sent = jsonDecode(request.body);
        return _ok(
            _json(title: 'Renamed', tags: const ['music'], category: 'comedy'));
      });
      final result = await server.repository().editDetails(
          OwnedVideo.fromJson(_json()),
          title: ' Renamed ',
          description: 'A story',
          category: 'comedy',
          tags: ['#Music']);
      expect(sent, {
        'title': 'Renamed',
        'category': 'comedy',
        'tags': ['music'],
      });
      expect(result.title, 'Renamed');
      expect(server.calls, ['PATCH /api/v1/videos/$_video']);
    });

    test('cover moment is sent as cover_time_ms and bounded by the duration',
        () async {
      late Object? sent;
      final withDuration = {..._json(), 'duration_ms': 90000};
      final server = _Server((request) {
        sent = jsonDecode(request.body);
        return _ok({...withDuration, 'cover_time_ms': 12000});
      });
      final video = OwnedVideo.fromJson(withDuration);
      final result =
          await server.repository().editDetails(video, coverTimeMs: 12000);
      expect(sent, {'cover_time_ms': 12000});
      expect(result.coverTimeMs, 12000);
      for (final bad in [-1, 90001, 300001]) {
        await expectLater(
            server.repository().editDetails(video, coverTimeMs: bad),
            throwsFormatException);
      }
      // Without a known duration the moment cannot be bounded, so it is refused.
      await expectLater(
          server
              .repository()
              .editDetails(OwnedVideo.fromJson(_json()), coverTimeMs: 1000),
          throwsFormatException);
      // The echo must carry the requested moment.
      final liar =
          _Server((_) => _ok({...withDuration, 'cover_time_ms': 3000}));
      await expectLater(
          liar.repository().editDetails(video, coverTimeMs: 12000),
          throwsFormatException);
    });

    test('edit refuses no-op, invalid and out-of-state requests locally',
        () async {
      final server = _Server((_) => _ok(_json()));
      final repository = server.repository();
      final video = OwnedVideo.fromJson(_json());
      for (final call in <Future<Object?> Function()>[
        () => repository.editDetails(video),
        () => repository.editDetails(video, title: 'My original'),
        () => repository.editDetails(video, title: '   '),
        () => repository.editDetails(video, title: 'x' * 161),
        () => repository.editDetails(video, description: 'x' * 2001),
        () => repository.editDetails(video, category: 'unknown'),
        () => repository.editDetails(video, tags: ['bad tag']),
        () => repository.editDetails(video,
            tags: List.filled(6, 'a')
                .asMap()
                .entries
                .map((e) => 't${e.key}')
                .toList()),
        () => repository.editDetails(
            OwnedVideo.fromJson(_json(state: 'review')),
            title: 'New'),
        () => repository.editDetails(
            OwnedVideo.fromJson(_json(state: 'removed')),
            title: 'New'),
      ]) {
        await expectLater(call(), throwsFormatException);
      }
      expect(server.calls, isEmpty);
    });

    test('edit refuses a response that ignored the change', () async {
      final server = _Server((_) => _ok(_json(title: 'Unchanged by server')));
      await expectLater(
          server
              .repository()
              .editDetails(OwnedVideo.fromJson(_json()), title: 'Renamed'),
          throwsFormatException);
    });

    test('delete works in any state and checks the confirmation', () async {
      for (final state in ['published', 'review', 'rejected', 'failed']) {
        final server =
            _Server((_) => _ok({'video_id': _video, 'deleted': true}));
        await server
            .repository()
            .deleteVideo(OwnedVideo.fromJson(_json(state: state)));
        expect(server.calls, ['DELETE /api/v1/videos/$_video']);
      }
      for (final body in [
        {'video_id': _video, 'deleted': false},
        {'video_id': _video},
        {'video_id': 'other', 'deleted': true},
      ]) {
        await expectLater(
            _Server((_) => _ok(body))
                .repository()
                .deleteVideo(OwnedVideo.fromJson(_json())),
            throwsFormatException);
      }
    });
  });

  group('controller', () {
    ManageVideoController build(_Server server) =>
        ManageVideoController(server.repository(), _video);

    test('loads, publishes once at a time and reports success', () async {
      var visibility = 'private';
      final server = _Server((request) {
        if (request.method == 'POST') visibility = 'public';
        return _ok(_json(visibility: visibility));
      });
      final controller = build(server);
      await controller.load();
      expect(controller.phase, ManagePhase.ready);
      final first = controller.publish();
      expect(controller.busy, isTrue);
      expect(await controller.publish(), isFalse); // double tap is ignored
      expect(await first, isTrue);
      expect(controller.video!.isPublic, isTrue);
      expect(controller.message, 'Your video is public.');
      expect(server.calls.where((c) => c.startsWith('POST')).length, 1);
    });

    test('maps every failure to a safe message and keeps the video', () async {
      final cases = <int, ({String? code, bool expired, String text})>{
        409: (code: 'review_required', expired: false, text: 'approved before'),
        401: (code: null, expired: true, text: 'Sign in'),
        403: (code: null, expired: false, text: 'cannot change'),
        404: (code: null, expired: false, text: 'no longer available'),
        429: (code: null, expired: false, text: 'Too many'),
        503: (code: null, expired: false, text: 'unavailable'),
      };
      for (final entry in cases.entries) {
        final server = _Server((request) {
          if (request.method == 'POST') {
            return entry.key == 401
                ? http.Response('{}', 401)
                : _ok({
                    'detail': 'internal service detail',
                    if (entry.value.code != null) 'code': entry.value.code
                  }, entry.key);
          }
          return _ok(_json());
        });
        final controller = build(server);
        await controller.load();
        expect(await controller.publish(), isFalse, reason: '${entry.key}');
        expect(controller.video, isNotNull);
        expect(controller.sessionExpired, entry.value.expired,
            reason: '${entry.key}');
        expect(controller.message, contains(entry.value.text));
        expect(controller.message, isNot(contains('internal service detail')));
        expect(controller.busy, isFalse);
      }
    });

    test('a failed load offers retry and a missing video is not found',
        () async {
      var up = false;
      final controller =
          build(_Server((_) => up ? _ok(_json()) : http.Response('{}', 404)));
      await controller.load();
      expect(controller.phase, ManagePhase.failed);
      up = true;
      await controller.load();
      expect(controller.phase, ManagePhase.ready);
    });

    test('delete marks the controller deleted', () async {
      final controller = build(_Server((request) => request.method == 'DELETE'
          ? _ok({'video_id': _video, 'deleted': true})
          : _ok(_json())));
      await controller.load();
      expect(await controller.delete(), isTrue);
      expect(controller.deleted, isTrue);
    });

    test('state labels are plain language and unknown states are not invented',
        () {
      expect(videoStateLabel(OwnedVideo.fromJson(_json(state: 'review'))),
          'Waiting for review');
      expect(videoStateLabel(OwnedVideo.fromJson(_json())),
          'Approved, not public');
      expect(videoStateLabel(OwnedVideo.fromJson(_json(visibility: 'public'))),
          'Public');
      expect(videoStateLabel(OwnedVideo.fromJson(_json(state: 'rejected'))),
          'Not approved');
    });
  });

  group('screen', () {
    Future<_Fake> pump(WidgetTester tester,
        {String state = 'published',
        String visibility = 'private',
        ApiFailure? onChange}) async {
      // A tall surface keeps the hero and every action on screen.
      tester.view.physicalSize = const Size(800, 3200);
      tester.view.devicePixelRatio = 2;
      addTearDown(tester.view.reset);
      final fake = _Fake(
          OwnedVideo.fromJson(_json(state: state, visibility: visibility)),
          onChange: onChange);
      await tester.pumpWidget(MaterialApp(
          home: LiveManageVideoScreen(videoId: _video, repository: fake)));
      await tester.pumpAndSettle();
      return fake;
    }

    testWidgets('an approved private video offers Publish, with confirmation',
        (tester) async {
      final fake = await pump(tester);
      expect(find.text('Approved, not public'), findsOneWidget);
      expect(find.text('Unpublish'), findsNothing);
      await tester.tap(find.text('Publish'));
      await tester.pumpAndSettle();
      expect(find.text('Publish this video?'), findsOneWidget);
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
      expect(fake.calls, isEmpty);
      await tester.tap(find.text('Publish'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Publish').last);
      await tester.pumpAndSettle();
      expect(find.text('Your video is public.'), findsOneWidget);
      expect(find.text('Unpublish'), findsOneWidget);
      expect(fake.calls, ['publish']);
    });

    testWidgets('a public video offers Unpublish with the M-055 confirmation',
        (tester) async {
      final fake = await pump(tester, visibility: 'public');
      await tester.tap(find.text('Unpublish'));
      await tester.pumpAndSettle();
      expect(find.text('Take this video off stage?'), findsOneWidget);
      await tester.tap(find.widgetWithText(FilledButton, 'Unpublish video'));
      await tester.pumpAndSettle();
      expect(find.text('Your video is no longer public.'), findsOneWidget);
      expect(find.text('Publish'), findsOneWidget);
      expect(fake.calls, ['unpublish']);
    });

    testWidgets('a rejected or removed video links to its notice (M-052)',
        (tester) async {
      tester.view.physicalSize = const Size(800, 3200);
      tester.view.devicePixelRatio = 2;
      addTearDown(tester.view.reset);
      final pushed = <RouteSettings>[];
      final fake = _Fake(OwnedVideo.fromJson(_json(state: 'rejected')));
      await tester.pumpWidget(MaterialApp(
          home: LiveManageVideoScreen(videoId: _video, repository: fake),
          onGenerateRoute: (settings) {
            pushed.add(settings);
            return MaterialPageRoute<void>(
                settings: settings, builder: (_) => const Scaffold());
          }));
      await tester.pumpAndSettle();
      expect(find.text('Publish'), findsNothing);
      await tester.tap(find.text('View notice'));
      await tester.pumpAndSettle();
      expect(pushed.last.name, const ScreenRoute(76).name);
    });

    testWidgets('a video in review cannot be published and says why',
        (tester) async {
      await pump(tester, state: 'review');
      expect(find.text('Publish'), findsNothing);
      expect(find.text('Unpublish'), findsNothing);
      expect(find.text('Waiting for review'), findsOneWidget);
      expect(find.textContaining('once it is approved'), findsOneWidget);
    });

    testWidgets('review_required from the server is explained, not retried',
        (tester) async {
      final fake = await pump(tester,
          onChange: const ApiFailure(409, 'x', code: 'review_required'));
      await tester.tap(find.text('Publish'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Publish').last);
      await tester.pumpAndSettle();
      expect(find.textContaining('must be approved'), findsOneWidget);
      expect(fake.calls, ['publish']);
    });

    testWidgets('an expired session during an action offers sign-in',
        (tester) async {
      await pump(tester, onChange: const ApiFailure(401, 'x'));
      await tester.tap(find.text('Publish'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Publish').last);
      await tester.pumpAndSettle();
      expect(find.text('Sign in'), findsOneWidget);
      expect(find.text('My original'),
          findsOneWidget); // the video stays on screen
    });

    testWidgets(
        'offline during an action keeps the video and says nothing changed',
        (tester) async {
      await pump(tester, onChange: const ApiFailure(503, 'x', offline: true));
      await tester.tap(find.text('Publish'));
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Publish').last);
      await tester.pumpAndSettle();
      expect(find.textContaining('offline'), findsOneWidget);
      expect(find.text('Publish'), findsOneWidget);
    });

    testWidgets('delete asks first and closes the screen', (tester) async {
      final fake = _Fake(OwnedVideo.fromJson(_json(state: 'rejected')));
      await tester.pumpWidget(MaterialApp(
          home: Builder(
              builder: (context) => Scaffold(
                  body: TextButton(
                      onPressed: () => Navigator.of(context).push(
                          MaterialPageRoute<bool>(
                              builder: (_) => LiveManageVideoScreen(
                                  videoId: _video, repository: fake))),
                      child: const Text('open'))))));
      tester.view.physicalSize = const Size(800, 3200);
      tester.view.devicePixelRatio = 2;
      addTearDown(tester.view.reset);
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Delete video'));
      await tester.tap(find.text('Delete video'));
      await tester.pumpAndSettle();
      expect(find.text('Delete this original?'), findsOneWidget);
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
      expect(fake.calls, isEmpty);
      await tester.tap(find.text('Delete video'));
      await tester.pumpAndSettle();
      // The destructive action stays disabled until DELETE is typed.
      expect(
          tester
              .widget<FilledButton>(
                  find.widgetWithText(FilledButton, 'Delete video'))
              .onPressed,
          isNull);
      await tester.enterText(find.byType(TextFormField), 'DELETE');
      await tester.pumpAndSettle();
      await tester.tap(find.widgetWithText(FilledButton, 'Delete video'));
      await tester.pumpAndSettle();
      expect(fake.calls, ['delete']);
      expect(find.byType(LiveManageVideoScreen), findsNothing);
    });

    testWidgets('edit validates tags locally before any request',
        (tester) async {
      final fake = await pump(tester);
      await tester.tap(find.text('Edit details'));
      await tester.pumpAndSettle();
      await tester.enterText(
          find.widgetWithText(TextFormField, 'Hashtags'), 'bad tag!');
      await tester.tap(find.text('Save'));
      await tester.pumpAndSettle();
      expect(find.textContaining('up to five tags'), findsOneWidget);
      expect(fake.calls, isEmpty);
    });

    testWidgets('a failed load offers retry', (tester) async {
      final fake = _Fake(OwnedVideo.fromJson(_json()), failLoads: 1);
      await tester.pumpWidget(MaterialApp(
          home: LiveManageVideoScreen(videoId: _video, repository: fake)));
      await tester.pumpAndSettle();
      expect(find.text('Try again'), findsOneWidget);
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('My original'), findsOneWidget);
    });

    testWidgets('text scale 2.0 keeps every action reachable', (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final fake = _Fake(OwnedVideo.fromJson(_json()));
      await tester.pumpWidget(MaterialApp(
          home: MediaQuery(
              data: const MediaQueryData(textScaler: TextScaler.linear(2)),
              child:
                  LiveManageVideoScreen(videoId: _video, repository: fake))));
      await tester.pumpAndSettle();
      for (final label in ['Publish', 'Edit details', 'Delete video']) {
        await tester.ensureVisible(find.text(label));
        expect(find.text(label), findsOneWidget);
      }
      expect(tester.takeException(), isNull);
    });
  });
}
