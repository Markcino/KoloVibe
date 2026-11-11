import '../../core/network/api_client.dart';

class LiveCreator {
  const LiveCreator(this.id, this.userId, this.handle, this.bio,
      {this.displayName = '',
      this.location = '',
      this.followerCount,
      this.publishedVideoCount});
  final String displayName, location;
  final int? followerCount, publishedVideoCount;
  final String id, userId, handle, bio;

  factory LiveCreator.fromJson(Map<String, dynamic> data) {
    final id = data['id'], userId = data['user_id'];
    final handle = data['handle'], bio = data['bio'];
    if (id is! String ||
        userId is! String ||
        handle is! String ||
        bio is! String ||
        data['status'] != 'active' ||
        !isApiId(id) ||
        !isApiId(userId) ||
        bio.length > 500 ||
        !RegExp(r'^[a-zA-Z0-9_-]{1,40}$').hasMatch(handle)) {
      throw const FormatException('Invalid creator');
    }
    final name = data['display_name'] ?? '', location = data['location'] ?? '';
    final followers = data['follower_count'],
        videos = data['published_video_count'];
    if (name is! String ||
        name.length > 80 ||
        location is! String ||
        location.length > 80 ||
        followers != null && (followers is! int || followers < 0) ||
        videos != null && (videos is! int || videos < 0)) {
      throw const FormatException('Invalid creator counts');
    }
    return LiveCreator(id, userId, handle, bio,
        displayName: name,
        location: location,
        followerCount: followers as int?,
        publishedVideoCount: videos as int?);
  }
}

class LiveCreatorRepository {
  const LiveCreatorRepository(this.api);
  final ApiClient api;

  Future<({List<LiveCreator> items, String? nextCursor})> search(String query,
      {String? cursor}) async {
    if (query.trim().isEmpty ||
        query.length > 100 ||
        cursor != null && !isApiId(cursor)) {
      throw const FormatException('Invalid creator search');
    }
    final data = await api.request('/creators/search', query: {
      'q': query,
      if (cursor != null) 'cursor': cursor,
    });
    final raw = data['items'];
    final next = data['next_cursor'];
    if (raw is! List || raw.length > 20 || !data.containsKey('next_cursor')) {
      throw const FormatException('Invalid creator search page');
    }
    final items = raw.map((item) {
      if (item is! Map<String, dynamic>) {
        throw const FormatException('Invalid creator');
      }
      return LiveCreator.fromJson(item);
    }).toList(growable: false);
    if (items.map((item) => item.id).toSet().length != items.length ||
        next != null &&
            (next is! String ||
                items.length != 20 ||
                next == cursor ||
                next != items.last.id)) {
      throw const FormatException('Invalid creator search cursor');
    }
    return (items: items, nextCursor: next as String?);
  }

  Future<LiveCreator> detail(String id) async {
    if (!isApiId(id)) throw const FormatException('Invalid creator identifier');
    final data = await api.request('/creators/$id');
    final creator = LiveCreator.fromJson(data);
    if (creator.id != id) throw const FormatException('Mismatched creator');
    return creator;
  }
}
