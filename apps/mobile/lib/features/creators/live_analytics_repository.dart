import '../../core/network/api_client.dart';
import '../account/live_account_repository.dart';

/// One day of the creator chart.
class AnalyticsDay {
  const AnalyticsDay(this.date, this.qualifiedPlays, this.likes);
  final DateTime date;
  final int qualifiedPlays, likes;
}

class TopOriginal {
  const TopOriginal(this.videoId, this.title, this.qualifiedPlays);
  final String videoId, title;
  final int qualifiedPlays;
}

/// `GET /creators/me/analytics?range=7d|28d`: qualified activity composed by
/// the gateway from the content and engagement services. Every number is the
/// service's own; nothing is estimated here.
class CreatorAnalytics {
  const CreatorAnalytics({
    required this.range,
    required this.totalVideos,
    required this.qualifiedPlays,
    required this.watchTimeSeconds,
    required this.likes,
    required this.newFollowers,
    required this.shares,
    required this.daily,
    required this.top,
  });
  final String range;
  final int totalVideos, qualifiedPlays, likes, newFollowers, shares;
  final double watchTimeSeconds;
  final List<AnalyticsDay> daily;
  final List<TopOriginal> top;

  /// No qualified activity at all: the designed "no data yet" state. Counts of
  /// zero are never presented as performance.
  bool get empty =>
      qualifiedPlays == 0 && likes == 0 && newFollowers == 0 && shares == 0;

  factory CreatorAnalytics.fromJson(Map<String, dynamic> data, String range) {
    int count(Object? value) {
      if (value is! int || value < 0) {
        throw const FormatException('Invalid analytics count');
      }
      return value;
    }

    double seconds(Object? value) {
      if (value is! num || !value.isFinite || value < 0) {
        throw const FormatException('Invalid analytics duration');
      }
      return value.toDouble();
    }

    if (data['range'] != range) {
      throw const FormatException('Mismatched analytics range');
    }
    final daily = data['daily'], top = data['top_videos'];
    if (daily is! List || top is! List || top.length > 5) {
      throw const FormatException('Invalid analytics lists');
    }
    final days = [
      for (final row in daily)
        if (row is Map<String, dynamic>)
          AnalyticsDay(DateTime.parse('${row['date']}T00:00:00Z'),
              count(row['qualified_plays']), count(row['likes']))
        else
          throw const FormatException('Invalid analytics day')
    ];
    final originals = [
      for (final row in top)
        if (row is Map<String, dynamic> &&
            row['video_id'] is String &&
            isApiId(row['video_id'] as String) &&
            row['title'] is String)
          TopOriginal(row['video_id'] as String, row['title'] as String,
              count(row['qualified_plays']))
        else
          throw const FormatException('Invalid top original')
    ];
    return CreatorAnalytics(
      range: range,
      totalVideos: count(data['total_videos']),
      qualifiedPlays: count(data['qualified_plays']),
      watchTimeSeconds: seconds(data['watch_time_seconds']),
      likes: count(data['likes']),
      newFollowers: count(data['new_followers']),
      shares: count(data['shares']),
      daily: days,
      top: originals,
    );
  }
}

/// `GET /creators/me/videos/{id}/analytics?range=7d|since_published`.
class VideoAnalytics {
  const VideoAnalytics({
    required this.videoId,
    required this.state,
    required this.range,
    required this.qualifiedPlays,
    required this.watchTimeSeconds,
    required this.likes,
    required this.shares,
    required this.averageWatchSeconds,
    required this.currentLikes,
  });
  final String videoId, state, range;
  final int qualifiedPlays, likes, shares, currentLikes;
  final double watchTimeSeconds, averageWatchSeconds;

  bool get empty => qualifiedPlays == 0 && likes == 0 && shares == 0;

  factory VideoAnalytics.fromJson(
      Map<String, dynamic> data, String videoId, String range) {
    int count(Object? value) {
      if (value is! int || value < 0) {
        throw const FormatException('Invalid analytics count');
      }
      return value;
    }

    double seconds(Object? value) {
      if (value is! num || !value.isFinite || value < 0) {
        throw const FormatException('Invalid analytics duration');
      }
      return value.toDouble();
    }

    if (data['video_id'] != videoId ||
        data['range'] != range ||
        data['state'] is! String) {
      throw const FormatException('Mismatched video analytics');
    }
    return VideoAnalytics(
      videoId: videoId,
      state: data['state'] as String,
      range: range,
      qualifiedPlays: count(data['qualified_plays']),
      watchTimeSeconds: seconds(data['watch_time_seconds']),
      likes: count(data['likes']),
      shares: count(data['shares']),
      averageWatchSeconds: seconds(data['average_watch_seconds']),
      currentLikes: count(data['current_likes']),
    );
  }
}

class LiveAnalyticsRepository {
  LiveAnalyticsRepository(this.account);
  final LiveAccountRepository account;

  Future<CreatorAnalytics> creator(String range) async {
    if (!const {'7d', '28d'}.contains(range)) {
      throw const FormatException('Invalid analytics range');
    }
    return CreatorAnalytics.fromJson(
        await account.authenticatedRequest('/creators/me/analytics',
            query: {'range': range}),
        range);
  }

  Future<VideoAnalytics> video(String videoId, String range) async {
    if (!isApiId(videoId) || !const {'7d', 'since_published'}.contains(range)) {
      throw const FormatException('Invalid analytics request');
    }
    return VideoAnalytics.fromJson(
        await account.authenticatedRequest(
            '/creators/me/videos/$videoId/analytics',
            query: {'range': range}),
        videoId,
        range);
  }
}
