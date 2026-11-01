import '../../core/network/api_client.dart';

class LiveCreator {
  const LiveCreator(this.id, this.userId, this.handle, this.bio);
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
    return LiveCreator(id, userId, handle, bio);
  }
}

class LiveCreatorRepository {
  const LiveCreatorRepository(this.api);
  final ApiClient api;

  Future<LiveCreator> detail(String id) async {
    if (!isApiId(id)) throw const FormatException('Invalid creator identifier');
    final data = await api.request('/creators/$id');
    final creator = LiveCreator.fromJson(data);
    if (creator.id != id) throw const FormatException('Mismatched creator');
    return creator;
  }
}
