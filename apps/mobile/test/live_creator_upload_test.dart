import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/security/credential_store.dart';
import 'package:kolovibe/features/account/live_account_repository.dart';
import 'package:kolovibe/features/content/live_content_repository.dart';
import 'package:kolovibe/features/creators/live_creator_onboarding_repository.dart';

class _Credentials implements CredentialStore {
  String? value = 'refresh';
  @override
  Future<void> clearRefreshToken() async => value = null;
  @override
  Future<String?> readRefreshToken() async => value;
  @override
  Future<void> writeRefreshToken(String token) async => value = token;
}

void main() {
  const accountId = '00000000-0000-4000-8000-000000000001';
  const creatorId = '00000000-0000-4000-8000-000000000002';
  const videoId = '00000000-0000-4000-8000-000000000003';
  const uploadId = '00000000-0000-4000-8000-000000000004';
  const key = 'a-unique-upload-key-1234';
  final expiry = DateTime.now().toUtc().add(const Duration(minutes: 5));

  /// The DOC-205 `OwnVideo` shape the gateway returns today.
  Map<String, Object?> ownVideoJson({
    String title = 'My original',
    String description = 'A story',
    String? category = 'culture',
    List<String> tags = const [],
    String state = 'draft',
  }) =>
      {
        'id': videoId,
        'creator_id': creatorId,
        'title': title,
        'description': description,
        'category': category,
        'tags': tags,
        'cover_time_ms': null,
        'state': state,
        'visibility': 'private',
        'created_at': '2026-11-11T10:00:00Z',
        'published_at': null,
        'poster_url': null,
      };

  test('creator invitation and eligibility use the current account', () async {
    var applicationStatus = 'invited';
    final account = LiveAccountRepository(
        ApiClient('https://api.example.test/api/v1',
            client: MockClient((request) async {
          if (request.url.path.endsWith('/auth/refresh')) {
            return http.Response(
                jsonEncode({
                  'access_token': 'access',
                  'refresh_token': 'rotated',
                }),
                200);
          }
          expect(request.headers['Authorization'], 'Bearer access');
          if (request.url.path.endsWith('/upload-eligibility')) {
            return http.Response(
                jsonEncode({
                  'upload_eligible': false,
                  'creator_id': null,
                }),
                200);
          }
          expect(request.url.path, '/api/v1/creators/me/application');
          if (request.method == 'POST') {
            expect(jsonDecode(request.body), {
              'handle': 'storyteller',
              'adult_attested': true,
              'rights_attested': true,
            });
            applicationStatus = 'pending';
          }
          return http.Response(
              jsonEncode({
                'account_id': accountId,
                'status': applicationStatus,
                'creator_id': null,
              }),
              200);
        })),
        _Credentials());
    final repository = LiveCreatorOnboardingRepository(account);
    expect((await repository.eligibility()).eligible, isFalse);
    expect((await repository.application())!.status, 'invited');
    await expectLater(
        repository.submit(
            handle: 'storyteller', adultAttested: false, rightsAttested: true),
        throwsFormatException);
    // DOC-205 requires ^[a-z0-9_]{3,30}$; the gateway answers 400 otherwise.
    await expectLater(
        repository.submit(
            handle: 'Storyteller', adultAttested: true, rightsAttested: true),
        throwsFormatException);
    expect(
        (await repository.submit(
                handle: ' storyteller ',
                adultAttested: true,
                rightsAttested: true))
            .status,
        'pending');
  });

  test('approved eligibility refreshes me before offering Studio', () async {
    for (final role in ['viewer', 'creator']) {
      final paths = <String>[];
      final account = LiveAccountRepository(
          ApiClient('https://api.example.test/api/v1',
              client: MockClient((request) async {
            paths.add(request.url.path);
            if (request.url.path.endsWith('/auth/refresh')) {
              return http.Response(
                  jsonEncode({
                    'access_token': 'access',
                    'refresh_token': 'rotated',
                  }),
                  200);
            }
            if (request.url.path.endsWith('/upload-eligibility')) {
              return http.Response(
                  jsonEncode({
                    'upload_eligible': true,
                    'creator_id': creatorId,
                  }),
                  200);
            }
            expect(request.url.path, '/api/v1/me');
            return http.Response(
                jsonEncode({
                  'id': accountId,
                  'email': 'creator@example.test',
                  'display_name': 'Creator',
                  'roles': [role],
                }),
                200);
          })),
          _Credentials());
      final repository = LiveCreatorOnboardingRepository(account);
      if (role == 'creator') {
        expect((await repository.eligibility()).eligible, isTrue);
      } else {
        await expectLater(
            repository.eligibility(),
            throwsA(isA<ApiFailure>()
                .having((failure) => failure.status, 'status', 503)));
      }
      expect(paths.last, '/api/v1/me');
    }
  });

  test('draft, signed upload, and completion use validated grants', () async {
    final gateway = MockClient((request) async {
      if (request.url.path.endsWith('/auth/refresh')) {
        return http.Response(
            jsonEncode({
              'access_token': 'access',
              'refresh_token': 'rotated',
            }),
            200);
      }
      expect(request.headers['Authorization'], 'Bearer access');
      if (request.url.path == '/api/v1/videos') {
        expect(request.headers['Idempotency-Key'], key);
        expect(jsonDecode(request.body), {
          'title': 'My original',
          'description': 'A story',
          'category': 'culture',
          'tags': ['monrovia', 'art'],
        });
        return http.Response(
            jsonEncode(ownVideoJson(
                title: 'My original',
                description: 'A story',
                category: 'culture',
                tags: ['monrovia', 'art'])),
            201);
      }
      if (request.url.path.endsWith('/upload-intents')) {
        expect(request.headers['Idempotency-Key'], key);
        expect(jsonDecode(request.body), {'size_bytes': 12});
        return http.Response(
            jsonEncode({
              'video_id': videoId,
              'upload_id': uploadId,
              'upload_url':
                  'https://media.example.test/upload?signature=opaque',
              'upload_headers': {
                'Content-Type': 'video/mp4',
                'Content-Length': '12',
                'If-None-Match': '*',
              },
              'expires_at': expiry.toIso8601String(),
              'max_bytes': 50 * 1024 * 1024,
            }),
            200);
      }
      expect(request.url.path, '/api/v1/videos/$videoId/upload-status');
      return http.Response(
          jsonEncode({
            'video_id': videoId,
            'state': 'processing',
            'failure_reason': null,
            'retryable': false,
          }),
          202);
    });
    final media = MockClient((request) async {
      expect(request.method, 'PUT');
      expect(request.url.queryParameters['signature'], 'opaque');
      expect(request.followRedirects, isFalse);
      expect(request.headers['Content-Type'], 'video/mp4');
      expect(request.headers['If-None-Match'], '*');
      expect(request.bodyBytes.length, 12);
      return http.Response('', 201);
    });
    final account = LiveAccountRepository(
        ApiClient('https://api.example.test/api/v1', client: gateway),
        _Credentials());
    final repository = LiveContentRepository(account, uploadClient: media);
    final draft = await repository.createDraft(
        title: ' My original ',
        description: 'A story',
        category: 'culture',
        tags: [' #Monrovia', 'ART', 'art'],
        idempotencyKey: key);
    final intent = await repository.reserveUpload(draft, 12, key);
    await repository.uploadToProvider(intent,
        Stream.value([0, 0, 0, 12, 0x66, 0x74, 0x79, 0x70, 0, 0, 0, 0]), 12);
    expect((await repository.completeUpload(draft.id)).state, 'processing');
  });

  test('upload grant rejects insecure host and mismatched content length', () {
    final data = {
      'video_id': videoId,
      'upload_id': uploadId,
      'upload_url': 'http://media.example.test/upload',
      'upload_headers': {
        'Content-Type': 'video/mp4',
        'Content-Length': '11',
        'If-None-Match': '*',
      },
      'expires_at': expiry.toIso8601String(),
      'max_bytes': 50 * 1024 * 1024,
    };
    expect(
        () => UploadIntent.fromJson(data, videoId, 12), throwsFormatException);
    expect(
        () => UploadIntent.fromJson(
            {...data, 'upload_url': 'https://media.example.test/upload'},
            videoId,
            12),
        throwsFormatException);
  });

  group('current gateway contract (DOC-205)', () {
    test('owned video accepts every field the gateway returns', () {
      final video = OwnedVideo.fromJson({
        ...ownVideoJson(tags: ['a_1', 'b']),
        'state': 'published',
        'visibility': 'public',
        'published_at': '2026-11-12T10:00:00+00:00',
        'cover_time_ms': 1500,
        'poster_url': 'https://media.example.test/poster.jpg?sig=x',
        'duration_seconds': 12,
        'duration_ms': 12040,
      });
      expect(video.category, 'culture');
      expect(video.tags, ['a_1', 'b']);
      expect(video.coverTimeMs, 1500);
      expect(video.durationMs, 12040);
      expect(video.publishedAt, isNotNull);
      expect(video.visibility, 'public');
    });

    test('owned video allows legacy rows without a category', () {
      expect(
          OwnedVideo.fromJson(ownVideoJson(category: null)).category, isNull);
    });

    test('owned video rejects drift instead of guessing', () {
      final good = ownVideoJson();
      final bad = <Map<String, Object?>>[
        // The pre-contract shape without the required fields.
        {
          'id': videoId,
          'creator_id': creatorId,
          'title': 'x',
          'description': '',
          'state': 'draft',
          'created_at': '2026-11-11T10:00:00Z',
        },
        {...good, 'extra': 1},
        {...good, 'category': 'news'},
        {
          ...good,
          'tags': ['Upper']
        },
        {
          ...good,
          'tags': ['a', 'a']
        },
        {
          ...good,
          'tags': ['a', 'b', 'c', 'd', 'e', 'f']
        },
        {...good, 'visibility': 'secret'},
        {...good, 'cover_time_ms': -1},
        {...good, 'duration_ms': 0},
        {...good, 'poster_url': 'http://media.example.test/p.jpg'},
        {...good, 'created_at': '2026-11-11T10:00:00'},
        {...good, 'published_at': 'soon'},
        {...good, 'state': 'archived'},
      ];
      for (final json in bad) {
        expect(() => OwnedVideo.fromJson(json), throwsFormatException,
            reason: '$json');
      }
    });

    test('library parses the current page shape', () async {
      final account = LiveAccountRepository(
          ApiClient('https://api.example.test/api/v1',
              client: MockClient((request) async {
            if (request.url.path.endsWith('/auth/refresh')) {
              return http.Response(
                  jsonEncode({'access_token': 'a', 'refresh_token': 'r'}), 200);
            }
            expect(request.url.path, '/api/v1/creators/me/videos');
            return http.Response(
                jsonEncode({
                  'items': [ownVideoJson(state: 'review')],
                  'next_cursor': null
                }),
                200);
          })),
          _Credentials());
      final page = await LiveContentRepository(account).library();
      expect(page.items.single.state, 'review');
      expect(page.items.single.category, 'culture');
    });

    test('draft requires a known category before any request is made',
        () async {
      var calls = 0;
      final account = LiveAccountRepository(
          ApiClient('https://api.example.test/api/v1',
              client: MockClient((request) async {
            calls++;
            return http.Response('{}', 500);
          })),
          _Credentials());
      final repository = LiveContentRepository(account);
      for (final category in ['', 'news', 'Culture']) {
        await expectLater(
            repository.createDraft(
                title: 'x',
                description: '',
                category: category,
                idempotencyKey: key),
            throwsFormatException);
      }
      await expectLater(
          repository.createDraft(
              title: 'x',
              description: '',
              category: 'culture',
              tags: ['not valid!'],
              idempotencyKey: key),
          throwsFormatException);
      expect(calls, 0);
    });

    test('draft response must echo the requested metadata', () async {
      final account = LiveAccountRepository(
          ApiClient('https://api.example.test/api/v1',
              client: MockClient((request) async {
            if (request.url.path.endsWith('/auth/refresh')) {
              return http.Response(
                  jsonEncode({'access_token': 'a', 'refresh_token': 'r'}), 200);
            }
            return http.Response(
                jsonEncode(ownVideoJson(category: 'comedy')), 201);
          })),
          _Credentials());
      await expectLater(
          LiveContentRepository(account).createDraft(
              title: 'My original',
              description: 'A story',
              category: 'culture',
              idempotencyKey: key),
          throwsFormatException);
    });

    test('upload status carries a failure reason and retry advice', () {
      VideoUploadStatus parse(String state, String? reason, bool retryable) =>
          VideoUploadStatus.fromJson({
            'video_id': videoId,
            'state': state,
            'failure_reason': reason,
            'retryable': retryable,
          }, videoId);
      expect(parse('failed', 'upload_missing', true).retryable, isTrue);
      expect(parse('processing', null, false).preparing, isTrue);
      expect(parse('processing', 'processing_unavailable', true).retryable,
          isTrue);
      expect(parse('review', null, false).state, 'review');
      // Retry advice that contradicts the state is rejected.
      expect(
          () => parse('failed', 'invalid_media', false), throwsFormatException);
      expect(() => parse('review', null, true), throwsFormatException);
      expect(() => parse('processing', null, true), throwsFormatException);
      expect(() => parse('failed', 'surprise', true), throwsFormatException);
      // The pre-contract two-field shape is rejected.
      expect(
          () => VideoUploadStatus.fromJson(
              {'video_id': videoId, 'state': 'processing'}, videoId),
          throwsFormatException);
    });

    test('hashtags are normalized like the server and bounded', () {
      expect(normalizeTags(['', '  ']), isEmpty);
      expect(() => normalizeTags(['#']), throwsFormatException);
      expect(normalizeTags(['#Monrovia', ' art ', 'ART']), ['monrovia', 'art']);
      expect(() => normalizeTags(['a b']), throwsFormatException);
      expect(() => normalizeTags(['x' * 31]), throwsFormatException);
      expect(() => normalizeTags(['1', '2', '3', '4', '5', '6']),
          throwsFormatException);
    });

    test('transfer reports progress and treats existing objects as success',
        () async {
      final intent = UploadIntent.fromJson({
        'video_id': videoId,
        'upload_id': uploadId,
        'upload_url': 'https://media.example.test/upload?signature=opaque',
        'upload_headers': {
          'Content-Type': 'video/mp4',
          'Content-Length': '12',
          'If-None-Match': '*',
        },
        'expires_at': expiry.toIso8601String(),
        'max_bytes': 50 * 1024 * 1024,
      }, videoId, 12);
      for (final status in [201, 412]) {
        final account = LiveAccountRepository(
            ApiClient('https://api.example.test/api/v1',
                client: MockClient((_) async => http.Response('{}', 500))),
            _Credentials());
        final repository = LiveContentRepository(account,
            uploadClient: MockClient((_) async => http.Response('', status)));
        final seen = <int>[];
        await repository.uploadToProvider(intent,
            Stream.fromIterable([List.filled(5, 0), List.filled(7, 0)]), 12,
            onProgress: seen.add);
        expect(seen, [5, 12]);
      }
      final failing = LiveContentRepository(
          LiveAccountRepository(
              ApiClient('https://api.example.test/api/v1',
                  client: MockClient((_) async => http.Response('{}', 500))),
              _Credentials()),
          uploadClient: MockClient((_) async => http.Response('', 403)));
      await expectLater(
          failing.uploadToProvider(
              intent, Stream.value(List.filled(12, 0)), 12),
          throwsA(isA<ApiFailure>()));
    });
  });
}
