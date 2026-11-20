import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/features/discovery/live_video_repository.dart';
import 'fl_a_support.dart';
import 'fl_b_repositories_test.dart' show videoJson, videoId;

/// D-6 (creator Popular) and D-9 (public play counts).
void main() {
  group('play label', () {
    test('has no label for zero or unknown, never a placeholder', () {
      expect(formatPlays(null), isNull);
      expect(formatPlays(0), isNull);
      expect(formatPlays(-3), isNull);
    });
    test('singular, plural and abbreviated values truncate, never round up',
        () {
      expect(formatPlays(1), '1 play');
      expect(formatPlays(2), '2 plays');
      expect(formatPlays(999), '999 plays');
      expect(formatPlays(1000), '1K plays');
      expect(formatPlays(1234), '1.2K plays');
      expect(formatPlays(1999), '1.9K plays');
      expect(formatPlays(999999), '999.9K plays');
      expect(formatPlays(1000000), '1M plays');
      expect(formatPlays(3456789), '3.4M plays');
    });
  });

  group('model', () {
    test('reads the aggregate and keeps unavailable as null, not zero', () {
      expect(LiveVideo.fromJson({...videoJson(), 'play_count': 41}).playCount,
          41);
      expect(LiveVideo.fromJson({...videoJson(), 'play_count': 0}).playCount,
          0);
      expect(LiveVideo.fromJson({...videoJson(), 'play_count': null}).playCount,
          isNull);
      expect(LiveVideo.fromJson(videoJson()).playCount, isNull);
    });
    test('rejects malformed counts', () {
      for (final bad in [-1, true, '5', 1.5]) {
        expect(() => LiveVideo.fromJson({...videoJson(), 'play_count': bad}),
            throwsFormatException);
      }
    });
  });

  group('repository', () {
    LiveVideoRepository repo(Map<String, String>? seen,
            [Map<String, Object?>? body]) =>
        LiveVideoRepository(ApiClient('https://api.example.test/api/v1',
            client: MockClient((request) async {
          seen?.addAll(request.url.queryParameters);
          return jsonResponse(body ??
              {
                'items': [
                  {...videoJson(), 'play_count': 9}
                ],
                'next_cursor': null
              });
        })));
    test('popular sends sort and the creator only', () async {
      final seen = <String, String>{};
      final page = await repo(seen).filteredPage(
          sort: 'popular', creatorId: '00000000-0000-4000-8000-000000000001');
      expect(seen,
          {'sort': 'popular', 'creator_id': '00000000-0000-4000-8000-000000000001'});
      expect(page.items.single.playCount, 9);
    });
    test('popular cannot be global, paged, searched or filtered', () async {
      final repository = repo(null);
      const creator = '00000000-0000-4000-8000-000000000001';
      for (final call in <Future<LiveVideoPage> Function()>[
        () => repository.filteredPage(sort: 'popular'),
        () => repository.filteredPage(
            sort: 'popular', creatorId: creator, cursor: videoId),
        () => repository.filteredPage(
            sort: 'popular', creatorId: creator, query: 'x'),
        () => repository.filteredPage(
            sort: 'popular', creatorId: creator, category: 'culture'),
        () => repository.filteredPage(sort: 'bogus'),
      ]) {
        await expectLater(call(), throwsFormatException);
      }
    });
    test('a failing popular request is an error, not a trending fallback',
        () async {
      final repository = LiveVideoRepository(ApiClient(
          'https://api.example.test/api/v1',
          client: MockClient((request) async {
        expect(request.url.queryParameters['sort'], 'popular');
        return http.Response('{"detail":"Content service unavailable"}', 503);
      })));
      await expectLater(
          repository.filteredPage(
              sort: 'popular',
              creatorId: '00000000-0000-4000-8000-000000000001'),
          throwsA(isA<ApiFailure>()));
    });
  });
}
