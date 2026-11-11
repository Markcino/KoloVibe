import '../../core/network/api_client.dart';
import '../account/live_account_repository.dart';

class LiveVideo {
  const LiveVideo(this.id, this.creatorId, this.title, this.description);
  final String id, creatorId, title, description;

  factory LiveVideo.fromJson(Map<String, dynamic> data) {
    final id = data['id'], creator = data['creator_id'];
    final title = data['title'], description = data['description'];
    if (id is! String ||
        creator is! String ||
        title is! String ||
        description is! String ||
        data['state'] != 'published' ||
        !isApiId(id) ||
        !isApiId(creator) ||
        title.isEmpty ||
        title.length > 160 ||
        description.length > 2000) {
      throw const FormatException('Invalid video');
    }

    return LiveVideo(id, creator, title, description);
  }
}

class LiveVideoPage {
  const LiveVideoPage(this.items, this.nextCursor);
  final List<LiveVideo> items;
  final String? nextCursor;
}

class LiveVideoRepository {
  const LiveVideoRepository(this.api);
  final ApiClient api;

  Future<LiveVideoPage> followingPage(LiveAccountRepository account,
      {String? cursor}) async {
    if (cursor != null && !isApiId(cursor)) {
      throw const FormatException('Invalid following cursor');
    }
    final response = await account.authenticatedRequest('/videos/following',
        query: {if (cursor != null) 'cursor': cursor});
    final raw = response['items'];
    final next = response['next_cursor'];
    if (raw is! List ||
        raw.length > 20 ||
        !response.containsKey('next_cursor')) {
      throw const FormatException('Invalid following feed');
    }
    final items = raw.map((value) {
      if (value is! Map<String, dynamic>) {
        throw const FormatException('Invalid video');
      }
      return LiveVideo.fromJson(value);
    }).toList(growable: false);
    if (items.map((item) => item.id).toSet().length != items.length ||
        next != null && (next is! String || !isApiId(next) || next == cursor)) {
      throw const FormatException('Invalid following cursor');
    }
    return LiveVideoPage(items, next as String?);
  }

  Future<List<LiveVideo>> list() async => (await page()).items;

  Future<LiveVideoPage> page(
      {String? cursor, String? creatorId, String? query}) async {
    if (cursor != null && !isApiId(cursor) ||
        creatorId != null && !isApiId(creatorId)) {
      throw const FormatException('Invalid video filter');
    }
    final response = await api.request('/videos', query: {
      if (cursor != null) 'cursor': cursor,
      if (query != null) 'q': query,
      if (creatorId != null) 'creator_id': creatorId,
    });
    final items = response['items'];
    if (items is! List || items.length > 20) {
      throw const FormatException('Invalid video list');
    }
    final videos = items.map((item) {
      if (item is! Map<String, dynamic>) {
        throw const FormatException('Invalid video');
      }
      return LiveVideo.fromJson(item);
    }).toList(growable: false);
    final next = response['next_cursor'];
    if (!response.containsKey('next_cursor') ||
        videos.map((video) => video.id).toSet().length != videos.length ||
        creatorId != null &&
            videos.any((video) => video.creatorId != creatorId) ||
        next != null &&
            (next is! String ||
                !isApiId(next) ||
                videos.length != 20 ||
                videos.last.id != next ||
                next == cursor)) {
      throw const FormatException('Invalid video page');
    }
    return LiveVideoPage(videos, next as String?);
  }

  Future<LiveVideo> detail(String id) async {
    if (!isApiId(id)) throw const FormatException('Invalid video identifier');
    final response = await api.request('/videos/$id');
    final video = LiveVideo.fromJson(response);
    if (video.id != id) throw const FormatException('Mismatched video');
    return video;
  }
}
