// Decision A (RV2-01): edits to a published video's text wait for review.
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
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
const _review = '00000000-0000-4000-8000-000000000004';

Map<String, Object?> _proposed({String title = 'Proposed'}) => {
      'title': title,
      'description': 'A story',
      'category': 'culture',
      'tags': <String>[]
    };

Map<String, Object?> _pending({String title = 'Proposed'}) => {
      'id': _review,
      'status': 'pending',
      'submitted_at': '2026-11-25T12:00:00Z',
      'decided_at': null,
      'reason_code': null,
      'proposed': _proposed(title: title),
    };

Map<String, Object?> _rejected() => {
      'id': _review,
      'status': 'rejected',
      'submitted_at': '2026-11-25T12:00:00Z',
      'decided_at': '2026-11-25T13:00:00Z',
      'reason_code': 'REVIEWED_EDIT_REJECT',
      'proposed': null,
    };

Map<String, Object?> _json({String state = 'published', Object? review}) => {
      'id': _video,
      'creator_id': _creator,
      'title': 'Live title',
      'description': 'A story',
      'category': 'culture',
      'tags': <String>[],
      'cover_time_ms': null,
      'state': state,
      'visibility': 'public',
      'created_at': '2026-11-11T10:00:00Z',
      'published_at': '2026-11-12T10:00:00Z',
      'poster_url': null,
      'edit_review': review,
    };

LiveContentRepository _repository(
        http.Response Function(http.Request) handler, List<Object?> sent) =>
    LiveContentRepository(LiveAccountRepository(
        ApiClient('https://api.example.test/api/v1',
            client: MockClient((request) async {
          if (request.url.path.endsWith('/auth/refresh')) {
            return http.Response(
                jsonEncode({'access_token': 'access', 'refresh_token': 'r2'}),
                200);
          }
          sent.add(request.body.isEmpty ? null : jsonDecode(request.body));
          return handler(request);
        })),
        _Credentials()));

http.Response _ok(Object body) => http.Response(jsonEncode(body), 200,
    headers: {'content-type': 'application/json'});

class _Fake extends LiveContentRepository {
  _Fake(this.video, this.next)
      : super(LiveAccountRepository(
            ApiClient('https://api.example.test/api/v1'), _Credentials()));
  OwnedVideo video;
  final OwnedVideo next;

  @override
  Future<OwnedVideo> ownedVideo(String videoId) async => video;

  @override
  Future<OwnedVideo> editDetails(OwnedVideo v,
          {String? title,
          String? description,
          String? category,
          List<String>? tags,
          int? coverTimeMs}) async =>
      video = next;
}

void main() {
  group('parsing', () {
    test('reads a pending, decided or absent edit review', () {
      final pending = OwnedVideo.fromJson(_json(review: _pending()));
      expect(pending.title, 'Live title');
      expect(pending.editReview!.isPending, isTrue);
      expect(pending.editingTitle, 'Proposed');
      final rejected = OwnedVideo.fromJson(_json(review: _rejected()));
      expect(rejected.editReview!.reasonCode, 'REVIEWED_EDIT_REJECT');
      expect(rejected.editingTitle, 'Live title');
      expect(OwnedVideo.fromJson(_json()).editReview, isNull);
    });

    test('rejects a malformed edit review', () {
      for (final bad in [
        _pending()..['decided_at'] = '2026-11-25T13:00:00Z',
        _rejected()..['proposed'] = _proposed(),
        _pending()..['status'] = 'superseded',
        _pending()..['reason_code'] = 'lower',
        _pending()..['proposed'] = {'title': 'x'},
        _pending()..['extra'] = 1,
      ]) {
        expect(() => OwnedVideo.fromJson(_json(review: bad)),
            throwsFormatException);
      }
    });
  });

  group('repository', () {
    test('a held edit is accepted when the proposal carries it', () async {
      final sent = <Object?>[];
      final result = await _repository(
              (_) => _ok(_json(review: _pending(title: 'New'))), sent)
          .editDetails(OwnedVideo.fromJson(_json()), title: 'New');
      expect(sent, [
        {'title': 'New'}
      ]);
      expect((result.title, result.editingTitle), ('Live title', 'New'));
    });

    test('a further edit is compared with the pending proposal', () async {
      final sent = <Object?>[];
      final video = OwnedVideo.fromJson(_json(review: _pending()));
      final repository = _repository((_) => _ok(_json()), sent);
      // Keeping the proposed title sends nothing; returning to the live title withdraws it.
      expect(() => repository.editDetails(video, title: 'Proposed'),
          throwsFormatException);
      final result = await repository.editDetails(video, title: 'Live title');
      expect(sent, [
        {'title': 'Live title'}
      ]);
      expect(result.editReview, isNull);
    });

    test('a proposal that ignores the edit is refused', () async {
      final repository = _repository(
          (_) => _ok(_json(review: _pending(title: 'Other'))), <Object?>[]);
      expect(
          () => repository.editDetails(OwnedVideo.fromJson(_json()),
              title: 'New'),
          throwsFormatException);
    });
  });

  group('screen', () {
    Future<void> pump(
        WidgetTester tester, OwnedVideo video, OwnedVideo next) async {
      tester.view.physicalSize = const Size(1200, 3000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(MaterialApp(
          home: LiveManageVideoScreen(
              videoId: _video,
              repository: _Fake(video, next),
              controller: null)));
      await tester.pumpAndSettle();
    }

    testWidgets('a pending edit says viewers still see the approved details',
        (tester) async {
      final video = OwnedVideo.fromJson(_json(review: _pending()));
      await pump(tester, video, video);
      expect(
          find.text(
              'Your changes are waiting for review. Viewers still see the approved details.'),
          findsOneWidget);
      expect(find.text('Live title'), findsOneWidget);
      await tester.tap(find.text('Edit details'));
      await tester.pumpAndSettle();
      expect(find.widgetWithText(TextFormField, 'Proposed'), findsOneWidget);
    });

    testWidgets(
        'a rejected edit is explained and a new save is sent for review',
        (tester) async {
      await pump(tester, OwnedVideo.fromJson(_json(review: _rejected())),
          OwnedVideo.fromJson(_json(review: _pending(title: 'Again'))));
      expect(
          find.text(
              'Your last changes were not approved. Viewers still see the approved details.'),
          findsOneWidget);
      await tester.tap(find.text('Edit details'));
      await tester.pumpAndSettle();
      await tester.enterText(
          find.widgetWithText(TextFormField, 'Live title'), 'Again');
      await tester.tap(find.text('Save'));
      await tester.pumpAndSettle();
      expect(find.text('Changes sent for review.'), findsOneWidget);
    });

    test('a draft edit shows no review note', () {
      expect(
          editReviewNote(OwnedVideo.fromJson(_json(state: 'draft'))), isNull);
      expect(ManageVideoController, isNotNull);
    });
  });
}
