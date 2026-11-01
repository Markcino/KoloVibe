import '../../core/network/api_client.dart';

class LiveVideo {
  const LiveVideo(this.id, this.creatorId, this.title, this.description);
  final String id, creatorId, title, description;

  factory LiveVideo.fromJson(Map<String, dynamic> data) {
    final id = data['id'], creator = data['creator_id'];
    final title = data['title'], description = data['description'];
    if (id is! String || creator is! String || title is! String ||
        description is! String || data['state'] != 'published') {
      throw const FormatException('Invalid video');
    }
    return LiveVideo(id, creator, title, description);
  }
}

class LiveVideoRepository {
  const LiveVideoRepository(this.api);
  final ApiClient api;

  Future<List<LiveVideo>> list() async {
    final response = await api.request('/videos');
    final items = response['items'];
    if (items is! List || items.length > 20) throw const FormatException('Invalid video list');
    return items.map((item) {
      if (item is! Map<String, dynamic>) throw const FormatException('Invalid video');
      return LiveVideo.fromJson(item);
    }).toList(growable: false);
  }

  Future<LiveVideo> detail(String id) async {
    final response = await api.request('/videos/$id');
    final video = LiveVideo.fromJson(response);
    if (video.id != id) throw const FormatException('Mismatched video');
    return video;
  }
}
