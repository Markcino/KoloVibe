import '../../core/network/api_client.dart';
import '../account/live_account_repository.dart';

class PlaybackGrant {
  const PlaybackGrant(this.url, this.expiresAt, this.sessionId);

  final Uri url;
  final DateTime expiresAt;
  final String? sessionId;

  factory PlaybackGrant.fromJson(Map<String, dynamic> value,
      {required bool tracked}) {
    final url = Uri.tryParse(
        value['playback_url'] is String ? value['playback_url'] as String : '');
    final expiry = DateTime.tryParse(
        value[tracked ? 'playback_expires_at' : 'expires_at'] is String
            ? value[tracked ? 'playback_expires_at' : 'expires_at'] as String
            : '');
    final session = value['session_id'];
    final sessionExpiry = tracked && value['session_expires_at'] is String
        ? DateTime.tryParse(value['session_expires_at'] as String)
        : null;
    if (url == null ||
        url.scheme != 'https' ||
        url.host.isEmpty ||
        url.userInfo.isNotEmpty ||
        url.hasFragment ||
        expiry == null ||
        !expiry.isAfter(DateTime.now()) ||
        tracked &&
            (session is! String ||
                !isApiId(session) ||
                sessionExpiry == null ||
                !sessionExpiry.isAfter(DateTime.now()))) {
      throw const FormatException('Invalid playback grant');
    }
    return PlaybackGrant(url, expiry, tracked ? session as String : null);
  }
}

class LiveVideoEngagementRepository {
  LiveVideoEngagementRepository(this.account);
  final LiveAccountRepository account;
  final Map<String, int?> likeCounts = {};
  void _count(String id, Map<String, dynamic> result) {
    if (result.length != 3 || !result.containsKey('like_count')) {
      throw const FormatException('Invalid like response');
    }
    final count = result['like_count'];
    if (count != null && (count is! int || count < 0)) {
      throw const FormatException('Invalid like count');
    }
    likeCounts[id] = count as int?;
  }

  Future<Uri> share(String videoId) async {
    final data = await account.authenticatedRequest('${_path(videoId)}/shares',
        method: 'POST');
    final raw = data['share_url'];
    final url = raw is String ? Uri.tryParse(raw) : null;
    if (data.length != 2 ||
        data['video_id'] != videoId ||
        url == null ||
        url.scheme != 'https' ||
        url.host.isEmpty ||
        url.userInfo.isNotEmpty ||
        url.hasFragment ||
        url.hasQuery ||
        url.path != '/videos/$videoId') {
      throw const FormatException('Invalid share response');
    }
    return url;
  }

  String _path(String id) {
    if (!isApiId(id)) throw const FormatException('Invalid video identifier');
    return '/videos/$id';
  }

  Future<bool> likeState(String videoId) async {
    final result = await account.authenticatedRequest('${_path(videoId)}/like');
    if (result['video_id'] != videoId || result['liked'] is! bool) {
      throw const FormatException('Invalid like state');
    }
    _count(videoId, result);
    return result['liked'] as bool;
  }

  Future<bool> setLiked(String videoId, bool liked) async {
    final result = await account.authenticatedRequest('${_path(videoId)}/like',
        method: liked ? 'PUT' : 'DELETE');
    if (!liked && result.isEmpty) return false;
    if (result['video_id'] != videoId || result['liked'] != liked) {
      throw const FormatException('Invalid like result');
    }
    _count(videoId, result);
    return liked;
  }

  Future<PlaybackGrant> startPlayback(String videoId) async {
    final path = _path(videoId);
    try {
      final grant = await account.authenticatedRequest('$path/watch-sessions',
          method: 'POST');
      return PlaybackGrant.fromJson(grant, tracked: true);
    } on ApiFailure catch (failure) {
      if (failure.status != 403 && failure.status != 409) rethrow;
      // Self views and unavailable tracking may still use an authorized grant.
      final grant = await account.authenticatedRequest('$path/playback');
      return PlaybackGrant.fromJson(grant, tracked: false);
    }
  }

  Future<bool> reportProgress(
      String videoId, String sessionId, int positionMs) async {
    if (!isApiId(videoId) ||
        !isApiId(sessionId) ||
        positionMs < 0 ||
        positionMs > 300000) {
      throw const FormatException('Invalid watch progress');
    }
    final result = await account.authenticatedRequest(
        '/engagement/watch-events',
        method: 'POST',
        body: {
          'video_id': videoId,
          'session_id': sessionId,
          'position_ms': positionMs,
        });
    if (result['qualified'] is! bool) {
      throw const FormatException('Invalid watch result');
    }
    return result['qualified'] as bool;
  }
}
