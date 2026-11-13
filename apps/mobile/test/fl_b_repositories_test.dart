import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/features/account/live_account_repository.dart';
import 'package:kolovibe/features/discovery/live_video_repository.dart';
import 'package:kolovibe/features/creators/live_creator_repository.dart';
import 'package:kolovibe/features/engagement/live_video_engagement_repository.dart';
import 'fl_a_support.dart';

const videoId = '00000000-0000-4000-8000-000000000003';
Map<String, Object?> videoJson([String id = videoId]) => {
      'id': id,
      'creator_id': accountId,
      'title': 'Waterside',
      'description': 'Original story',
      'state': 'published',
      'visibility': 'public',
      'category': 'culture',
      'tags': ['original'],
      'published_at': '2026-11-11T12:00:00Z',
      'like_count': 12,
      'poster_url': 'https://media.example.test/poster'
    };
Map<String, Object?> creatorJson() => {
      'id': accountId,
      'handle': 'mark',
      'bio': 'Stories',
      'display_name': 'Mark',
      'location': 'Monrovia',
      'status': 'active',
      'follower_count': 7,
      'published_video_count': 2
    };
Map<String, Object?> playbackJson() => {
      'playback_url': 'https://media.example.test/signed/video',
      'expires_at': DateTime.now()
          .toUtc()
          .add(const Duration(minutes: 5))
          .toIso8601String()
    };
void main() {
  for (final category in videoCategories) {
    test('category $category and query are sent without synthetic records',
        () async {
      final repository = LiveVideoRepository(
          ApiClient('https://api.example.test/api/v1',
              client: MockClient((request) async {
        expect(request.url.queryParameters,
            {'category': category, 'q': 'Waterside'});
        return jsonResponse({
          'items': [
            {...videoJson(), 'category': category}
          ],
          'next_cursor': null
        });
      })));
      expect(
          (await repository.filteredPage(
                  category: category, query: 'Waterside'))
              .items
              .single
              .category,
          category);
    });
  }
  test('trending and creator filters preserve server order and counts',
      () async {
    final repository = LiveVideoRepository(ApiClient(
        'https://api.example.test/api/v1', client: MockClient((request) async {
      expect(request.url.queryParameters,
          {'sort': 'trending', 'creator_id': accountId});
      return jsonResponse({
        'items': [videoJson(receiptId), videoJson()],
        'next_cursor': null
      });
    })));
    final page =
        await repository.filteredPage(sort: 'trending', creatorId: accountId);
    expect(page.items.map((v) => v.id), [receiptId, videoId]);
    expect(page.items.first.likeCount, 12);
    expect(page.items.first.posterUrl!.scheme, 'https');
  });
  for (final bad in [
    {...videoJson(), 'id': 'bad'},
    {...videoJson(), 'state': 'draft'},
    {...videoJson(), 'visibility': 'private'},
    {...videoJson(), 'category': 'fake'},
    {...videoJson(), 'like_count': -1},
    {...videoJson(), 'like_count': true},
    {...videoJson(), 'poster_url': 'http://unsafe.test'},
    {
      ...videoJson(),
      'tags': ['Bad Tag']
    },
    {...videoJson(), 'tags': List.filled(6, 'tag')},
    {...videoJson(), 'published_at': 'invalid'},
    {...videoJson(), 'deleted_at': '2026-11-11T12:00:00Z'},
  ]) {
    test(
        'malformed public video is rejected: ${bad.keys.where((k) => bad[k].toString() != videoJson()[k].toString()).join()}',
        () {
      expect(() => LiveVideo.fromJson(bad), throwsFormatException);
    });
  }
  for (final bad in [
    {...creatorJson(), 'display_name': 1},
    {...creatorJson(), 'location': List.filled(81, 'x').join()},
    {...creatorJson(), 'follower_count': -1},
    {...creatorJson(), 'published_video_count': '2'},
    {...creatorJson(), 'status': 'suspended'},
  ]) {
    test('invalid public creator rejected ${bad.toString()}',
        () => expect(() => LiveCreator.fromJson(bad), throwsFormatException));
  }
  test('public creator needs no account id and ignores one if sent', () {
    expect(creatorJson().containsKey('user_id'), isFalse);
    expect(LiveCreator.fromJson(creatorJson()).handle, 'mark');
    final leaked = LiveCreator.fromJson(
        {...creatorJson(), 'user_id': '00000000-0000-4000-8000-0000000000ff'});
    expect(leaked.id, creatorJson()['id']);
    expect(leaked.toString(), isNot(contains('00000000-0000-4000-8000-0000000000ff')));
  });
  test('public creator with a malformed id is still rejected', () {
    expect(() => LiveCreator.fromJson({...creatorJson(), 'id': 'not-an-id'}),
        throwsFormatException);
  });
  test('unknown counters remain null, never invented zero', () {
    final video = LiveVideo.fromJson({
      ...videoJson(),
      'like_count': null,
      'poster_url': null,
      'category': null
    });
    expect(video.likeCount, isNull);
    expect(video.posterUrl, isNull);
    expect(
        LiveCreator.fromJson({...creatorJson(), 'follower_count': null})
            .followerCount,
        isNull);
  });
  final operations = [
    'list',
    'following',
    'detail',
    'playback',
    'creator',
    'search',
    'like',
    'unlike',
    'share',
    'progress'
  ];
  for (final operation in operations) {
    for (final status in [401, 403, 404, 409, 429, 503, 0]) {
      test('$operation preserves failure $status', () async {
        final client = MockClient((request) async {
          if (request.url.path.endsWith('/auth/refresh')) {
            return jsonResponse(
                {'access_token': 'access', 'refresh_token': 'refresh'});
          }
          if (status == 0) throw http.ClientException('Offline');
          return jsonResponse(
              {'detail': 'Unavailable', 'code': 'share_unavailable'}, status);
        });
        final api =
            ApiClient('https://api.example.test/api/v1', client: client);
        final account = LiveAccountRepository(api, MemoryStore());
        final videos = LiveVideoRepository(api),
            creators = LiveCreatorRepository(api),
            engagement = LiveVideoEngagementRepository(account);
        final Future<Object?> result = switch (operation) {
          'list' => videos.filteredPage(),
          'following' => videos.followingPage(account),
          'detail' => videos.detail(videoId),
          'playback' => videos.playback(videoId),
          'creator' => creators.detail(accountId),
          'search' => creators.search('mark'),
          'like' => engagement.setLiked(videoId, true),
          'unlike' => engagement.setLiked(videoId, false),
          'share' => engagement.share(videoId),
          _ => engagement.reportProgress(videoId, receiptId, 3000),
        };
        await expectLater(
            result,
            throwsA(isA<ApiFailure>()
                .having((f) => f.status, 'status', status == 0 ? 503 : status)
                .having((f) => f.offline, 'offline', status == 0)));
      });
    }
  }
  test('like counts update from real GET/PUT/DELETE responses', () async {
    final fixture = AccountFixture(
        handler: (request) async => jsonResponse({
              'video_id': videoId,
              'liked': request.method == 'PUT',
              'like_count': request.method == 'PUT' ? 13 : 12
            }));
    final repository = LiveVideoEngagementRepository(fixture.account);
    expect(await repository.likeState(videoId), isFalse);
    expect(repository.likeCounts[videoId], 12);
    await repository.setLiked(videoId, true);
    expect(repository.likeCounts[videoId], 13);
    await repository.setLiked(videoId, false);
    expect(repository.likeCounts[videoId], 12);
  });
  test(
      'watch events carry observed position only, never qualification or points',
      () async {
    final fixture = AccountFixture(handler: (request) async {
      expect(jsonDecode(request.body),
          {'video_id': videoId, 'session_id': receiptId, 'position_ms': 3000});
      return jsonResponse({'qualified': false});
    });
    expect(
        await LiveVideoEngagementRepository(fixture.account)
            .reportProgress(videoId, receiptId, 3000),
        isFalse);
  });
  for (final raw in [
    'http://unsafe.test/videos/$videoId',
    'https://user@web.test/videos/$videoId',
    'https://web.test/videos/$receiptId',
    'https://web.test/videos/$videoId?secret=value'
  ]) {
    test('unsafe/mismatched share URL rejected $raw', () async {
      final fixture = AccountFixture(
          handler: (_) async =>
              jsonResponse({'video_id': videoId, 'share_url': raw}));
      await expectLater(
          LiveVideoEngagementRepository(fixture.account).share(videoId),
          throwsFormatException);
    });
  }
  test('malformed like response is not acknowledged', () async {
    final fixture = AccountFixture(
        handler: (_) async => jsonResponse(
            {'video_id': videoId, 'liked': true, 'like_count': '1'}));
    await expectLater(
        LiveVideoEngagementRepository(fixture.account).setLiked(videoId, true),
        throwsFormatException);
  });
  test('repeated cursor and category mismatch fail closed', () async {
    final repository =
        LiveVideoRepository(ApiClient('https://api.example.test/api/v1',
            client: MockClient((_) async => jsonResponse({
                  'items': [videoJson()],
                  'next_cursor': videoId
                }))));
    await expectLater(
        repository.filteredPage(category: 'hipco'), throwsFormatException);
    await expectLater(
        repository.filteredPage(cursor: videoId), throwsFormatException);
    await expectLater(
        repository.filteredPage(sort: 'trending', cursor: videoId),
        throwsFormatException);
  });
}
