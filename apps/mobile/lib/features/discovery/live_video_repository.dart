import '../../core/network/api_client.dart';
import '../account/live_account_repository.dart';
import '../engagement/live_video_engagement_repository.dart';

const videoCategories = {
  'hipco',
  'afrobeats',
  'comedy',
  'skits',
  'short_films',
  'culture',
  'documentaries'
};
Uri? mediaPoster(Object? value) {
  if (value == null) return null;
  if (value is! String) throw const FormatException('Invalid poster');
  final url = Uri.tryParse(value);
  if (url == null ||
      url.scheme != 'https' ||
      url.host.isEmpty ||
      url.userInfo.isNotEmpty ||
      url.hasFragment) {
    throw const FormatException('Invalid poster');
  }
  return url;
}

class LiveVideo {
  const LiveVideo(this.id, this.creatorId, this.title, this.description,
      {this.category,
      this.posterUrl,
      this.likeCount,
      this.playCount,
      this.publishedAt,
      this.durationMs,
      this.tags = const []});
  final String? category;
  final int? durationMs;
  final Uri? posterUrl;
  final int? likeCount;

  /// All-time server-qualified plays (D-9); null when the service could not say.
  final int? playCount;
  final DateTime? publishedAt;
  final List<String> tags;
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

    final category = data['category'],
        count = data['like_count'],
        plays = data['play_count'],
        tags = data['tags'] ?? [];
    final published = data['published_at'];
    // The public contract carries an optional duration, in milliseconds or in
    // whole seconds; neither is invented when absent.
    final millis = data['duration_ms'], seconds = data['duration_seconds'];
    if (millis != null && (millis is! int || millis < 1 || millis > 300000) ||
        seconds != null && (seconds is! int || seconds < 0 || seconds > 300)) {
      throw const FormatException('Invalid video duration');
    }
    if (category != null && !videoCategories.contains(category) ||
        count != null && (count is! int || count < 0) ||
        plays != null && (plays is! int || plays < 0) ||
        tags is! List ||
        tags.length > 5 ||
        tags.any((tag) =>
            tag is! String || !RegExp(r'^[a-z0-9_]{1,30}$').hasMatch(tag)) ||
        data['visibility'] != null && data['visibility'] != 'public' ||
        data['deleted_at'] != null ||
        published != null &&
            (published is! String || DateTime.tryParse(published) == null)) {
      throw const FormatException('Invalid public video metadata');
    }
    return LiveVideo(id, creator, title, description,
        category: category as String?,
        posterUrl: mediaPoster(data['poster_url']),
        likeCount: count as int?,
        playCount: plays as int?,
        durationMs: millis as int? ??
            (seconds == null ? null : (seconds as int) * 1000),
        tags: tags.cast<String>(),
        publishedAt:
            published == null ? null : DateTime.parse(published as String));
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
    return filteredPage(cursor: cursor, creatorId: creatorId, query: query);
  }

  Future<LiveVideoPage> filteredPage(
      {String? cursor,
      String? creatorId,
      String? query,
      String? category,
      String sort = 'recent'}) async {
    if (category != null && !videoCategories.contains(category) ||
        !{'recent', 'trending', 'popular'}.contains(sort) ||
        sort == 'trending' && cursor != null ||
        // Popular is one creator's order: nothing else may narrow or page it.
        sort == 'popular' &&
            (creatorId == null ||
                cursor != null ||
                query != null ||
                category != null) ||
        query != null &&
            (query.trim().isEmpty ||
                query.length > 100 ||
                query.codeUnits.any((c) => c < 32))) {
      throw const FormatException('Invalid filter');
    }
    if (cursor != null && !isApiId(cursor) ||
        creatorId != null && !isApiId(creatorId)) {
      throw const FormatException('Invalid video filter');
    }
    final response = await api.request('/videos', query: {
      if (category != null) 'category': category,
      if (sort != 'recent') 'sort': sort,
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
        sort == 'trending' && next != null ||
        category != null && videos.any((video) => video.category != category) ||
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

  Future<PlaybackGrant> playback(String id,
      {LiveAccountRepository? account}) async {
    if (!isApiId(id)) throw const FormatException('Invalid video identifier');
    return PlaybackGrant.fromJson(
        account == null
            ? await api.request('/videos/$id/playback')
            : await account.authenticatedRequest('/videos/$id/playback'),
        tracked: false);
  }

  Future<LiveVideo> detail(String id) async {
    if (!isApiId(id)) throw const FormatException('Invalid video identifier');
    final response = await api.request('/videos/$id');
    final video = LiveVideo.fromJson(response);
    if (video.id != id) throw const FormatException('Mismatched video');
    return video;
  }
}

/// `03:12` style duration, or null when the service did not supply one.
String? formatDuration(int? milliseconds) {
  if (milliseconds == null || milliseconds <= 0) return null;
  final total = (milliseconds / 1000).round();
  return '${(total ~/ 60).toString().padLeft(2, '0')}:${(total % 60).toString().padLeft(2, '0')}';
}

/// Public play label (D-9): `1 play`, `12 plays`, `1.2K plays`, `3.4M plays`. Zero and unknown
/// counts have no label, so the interface never shows "0 plays" or a placeholder for a missing count.
String? formatPlays(int? count) {
  if (count == null || count <= 0) return null;
  String scaled(double value, String unit) {
    final rounded = (value * 10).floor() / 10; // truncate: never claim more than was counted
    final text = rounded == rounded.roundToDouble()
        ? rounded.toStringAsFixed(0)
        : rounded.toStringAsFixed(1);
    return '$text$unit plays';
  }

  if (count == 1) return '1 play';
  if (count < 1000) return '$count plays';
  if (count < 1000000) return scaled(count / 1000, 'K');
  return scaled(count / 1000000, 'M');
}
