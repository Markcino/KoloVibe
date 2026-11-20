import 'dart:async';
import 'package:http/http.dart' as http;
import '../../core/network/api_client.dart';
import '../account/live_account_repository.dart';

/// DOC-205 `category` values accepted by the server, with display labels.
const videoCategories = <String, String>{
  'hipco': 'Hipco',
  'afrobeats': 'Afrobeats',
  'comedy': 'Comedy',
  'skits': 'Skits',
  'short_films': 'Short films',
  'culture': 'Culture',
  'documentaries': 'Documentaries',
};

const _videoStates = {
  'draft',
  'uploading',
  'processing',
  'failed',
  'review',
  'published',
  'rejected',
  'removed'
};

final _tagPattern = RegExp(r'^[a-z0-9_]{1,30}$');

/// Mirrors the server rule: trim, drop one leading `#`, lowercase, deduplicate.
/// Throws [FormatException] when any tag is invalid or more than five remain.
List<String> normalizeTags(Iterable<String> raw) {
  final tags = <String>[];
  for (final item in raw) {
    var tag = item.trim();
    if (tag.isEmpty) continue;
    if (tag.length > 64) throw const FormatException('Invalid hashtag');
    if (tag.startsWith('#')) tag = tag.substring(1);
    tag = tag.toLowerCase();
    if (!_tagPattern.hasMatch(tag)) {
      throw const FormatException('Invalid hashtag');
    }
    if (!tags.contains(tag)) tags.add(tag);
  }
  if (tags.length > 5) throw const FormatException('Too many hashtags');
  return List.unmodifiable(tags);
}

class OwnedVideo {
  const OwnedVideo(this.id, this.creatorId, this.title, this.description,
      this.state, this.createdAt,
      {this.category,
      this.tags = const [],
      this.coverTimeMs,
      this.visibility = 'private',
      this.publishedAt,
      this.posterUrl,
      this.durationMs,
      this.revision});

  final String id, creatorId, title, description, state, visibility;
  final DateTime createdAt;
  final String? category;
  final List<String> tags;
  final int? coverTimeMs, durationMs;
  final DateTime? publishedAt;

  /// Moderation revision; only the owned-detail read returns it.
  final int? revision;

  /// Short-lived signed URL (at most 300 seconds). Never persist it.
  final String? posterUrl;

  bool get canEditDraft => state == 'draft';

  /// Moderation approved the video; the creator decides whether it is public.
  bool get isApproved => state == 'published';
  bool get isPublic => isApproved && visibility == 'public';
  bool get canPublish => isApproved && visibility != 'public';
  bool get canUnpublish => isPublic;

  /// DOC-205 allows editing details in these states (a published edit keeps its approval).
  bool get canEditDetails =>
      const {'draft', 'failed', 'rejected', 'published'}.contains(state);

  factory OwnedVideo.fromJson(Object? raw) {
    const required = {
      'id',
      'creator_id',
      'title',
      'description',
      'category',
      'tags',
      'cover_time_ms',
      'state',
      'visibility',
      'created_at',
      'published_at',
      'poster_url'
    };
    if (raw is! Map<String, dynamic> ||
        !raw.keys.toSet().containsAll(required) ||
        raw.keys.toSet().difference({
          ...required,
          'duration_seconds',
          'duration_ms',
          'revision'
        }).isNotEmpty) {
      throw const FormatException('Invalid owned video');
    }
    final id = raw['id'];
    final creatorId = raw['creator_id'];
    final title = raw['title'];
    final description = raw['description'];
    final state = raw['state'];
    final visibility = raw['visibility'];
    final category = raw['category'];
    final rawTags = raw['tags'];
    final cover = raw['cover_time_ms'];
    final poster = raw['poster_url'];
    final seconds = raw['duration_seconds'];
    final millis = raw['duration_ms'];
    final revision = raw['revision'];
    if (!isApiId(id) ||
        !isApiId(creatorId) ||
        title is! String ||
        title.isEmpty ||
        title.length > 160 ||
        description is! String ||
        description.length > 2000 ||
        state is! String ||
        !_videoStates.contains(state) ||
        !{'private', 'public', 'unlisted'}.contains(visibility) ||
        category != null && !videoCategories.containsKey(category) ||
        rawTags is! List ||
        rawTags.length > 5 ||
        rawTags.any((tag) => tag is! String || !_tagPattern.hasMatch(tag)) ||
        rawTags.toSet().length != rawTags.length ||
        cover != null && (cover is! int || cover < 0 || cover > 300000) ||
        seconds != null && (seconds is! int || seconds < 0 || seconds > 300) ||
        millis != null && (millis is! int || millis < 1 || millis > 300000) ||
        revision != null &&
            (revision is! int || revision < 0 || revision > 2147483647) ||
        poster != null &&
            (poster is! String ||
                poster.length > 4096 ||
                Uri.tryParse(poster)?.scheme != 'https')) {
      throw const FormatException('Invalid owned video');
    }
    final created = _timestamp(raw['created_at']);
    final published =
        raw['published_at'] == null ? null : _timestamp(raw['published_at']);
    return OwnedVideo(
        id as String, creatorId as String, title, description, state, created,
        category: category as String?,
        tags: List<String>.unmodifiable(rawTags.cast<String>()),
        coverTimeMs: cover as int?,
        visibility: visibility as String,
        publishedAt: published,
        posterUrl: poster as String?,
        revision: revision as int?,
        durationMs: millis as int? ??
            (seconds == null ? null : (seconds as int) * 1000));
  }

  static DateTime _timestamp(Object? value) {
    final parsed = value is String ? DateTime.tryParse(value) : null;
    if (parsed == null ||
        !(value as String).contains(RegExp(r'(Z|[+-]\d\d:\d\d)$'))) {
      throw const FormatException('Invalid video timestamp');
    }
    return parsed;
  }
}

class OwnedVideoPage {
  const OwnedVideoPage(this.items, this.nextCursor);

  final List<OwnedVideo> items;
  final String? nextCursor;
}

class UploadIntent {
  const UploadIntent(this.videoId, this.uploadId, this.url, this.headers,
      this.expiresAt, this.maxBytes);

  final String videoId, uploadId;
  final Uri url;
  final Map<String, String> headers;
  final DateTime expiresAt;
  final int maxBytes;

  factory UploadIntent.fromJson(
      Map<String, dynamic> data, String videoId, int sizeBytes) {
    final url = data['upload_url'] is String
        ? Uri.tryParse(data['upload_url'] as String)
        : null;
    final expiresAt = data['expires_at'] is String
        ? DateTime.tryParse(data['expires_at'] as String)
        : null;
    final headers = data['upload_headers'];
    if (data.keys.toSet().difference({
          'video_id',
          'upload_id',
          'upload_url',
          'upload_headers',
          'expires_at',
          'max_bytes'
        }).isNotEmpty ||
        data['video_id'] != videoId ||
        !isApiId(data['upload_id']) ||
        url == null ||
        url.scheme != 'https' ||
        url.host.isEmpty ||
        url.userInfo.isNotEmpty ||
        url.hasFragment ||
        expiresAt == null ||
        !expiresAt.isAfter(DateTime.now()) ||
        data['max_bytes'] != 50 * 1024 * 1024 ||
        headers is! Map<String, dynamic> ||
        headers.length != 3 ||
        headers['Content-Type'] != 'video/mp4' ||
        headers['Content-Length'] != '$sizeBytes' ||
        headers['If-None-Match'] != '*') {
      throw const FormatException('Invalid upload grant');
    }
    return UploadIntent(
        videoId,
        data['upload_id'] as String,
        url,
        Map.unmodifiable(headers.cast<String, String>()),
        expiresAt,
        data['max_bytes'] as int);
  }
}

const _failureReasons = {
  'invalid_media',
  'cover_out_of_range',
  'processing_unavailable',
  'poster_failed',
  'upload_missing',
  'upload_changed'
};

class VideoUploadStatus {
  const VideoUploadStatus(this.videoId, this.state,
      {this.failureReason, this.retryable = false});
  final String videoId, state;

  /// Stable server reason for a failed or interrupted preparation, else null.
  final String? failureReason;

  /// The server's statement that the owner may retry the upload or completion.
  final bool retryable;

  bool get preparing => state == 'uploading' || state == 'processing';

  factory VideoUploadStatus.fromJson(
      Map<String, dynamic> data, String videoId) {
    final state = data['state'];
    final reason = data['failure_reason'];
    final retryable = data['retryable'];
    if (data.keys.toSet().difference(
            {'video_id', 'state', 'failure_reason', 'retryable'}).isNotEmpty ||
        data.length != 4 ||
        data['video_id'] != videoId ||
        state is! String ||
        !_videoStates.contains(state) ||
        reason != null &&
            (reason is! String || !_failureReasons.contains(reason)) ||
        retryable is! bool ||
        // Retry is offered for draft/uploading/failed, and for processing
        // only when a transient failure reason is present.
        retryable !=
            ({'draft', 'uploading', 'failed'}.contains(state) ||
                state == 'processing' && reason != null)) {
      throw const FormatException('Invalid upload status');
    }
    return VideoUploadStatus(videoId, state,
        failureReason: reason as String?, retryable: retryable);
  }
}

class LiveContentRepository {
  const LiveContentRepository(this.account, {this.uploadClient});

  final LiveAccountRepository account;
  final http.Client? uploadClient;

  Future<OwnedVideo> createDraft(
      {required String title,
      required String description,
      required String category,
      List<String> tags = const [],
      required String idempotencyKey}) async {
    final cleaned = title.trim();
    if (cleaned.isEmpty ||
        cleaned.length > 160 ||
        description.length > 2000 ||
        !videoCategories.containsKey(category)) {
      throw const FormatException('Invalid draft metadata');
    }
    final normalized = normalizeTags(tags);
    final result = OwnedVideo.fromJson(await account.authenticatedRequest(
        '/videos',
        method: 'POST',
        idempotencyKey: idempotencyKey,
        body: {
          'title': cleaned,
          'description': description,
          'category': category,
          'tags': normalized,
        }));
    if (!result.canEditDraft ||
        result.category != category ||
        result.title != cleaned) {
      throw const FormatException('Invalid draft response');
    }
    return result;
  }

  Future<UploadIntent> reserveUpload(
      OwnedVideo video, int sizeBytes, String idempotencyKey) async {
    if (!isApiId(video.id) ||
        !{'draft', 'uploading'}.contains(video.state) ||
        sizeBytes < 1 ||
        sizeBytes > 50 * 1024 * 1024) {
      throw const FormatException('Invalid upload reservation');
    }
    final result = await account.authenticatedRequest(
        '/videos/${video.id}/upload-intents',
        method: 'POST',
        idempotencyKey: idempotencyKey,
        body: {'size_bytes': sizeBytes});
    return UploadIntent.fromJson(result, video.id, sizeBytes);
  }

  Future<void> uploadToProvider(
      UploadIntent intent, Stream<List<int>> bytes, int sizeBytes,
      {void Function(int sentBytes)? onProgress}) async {
    if (intent.expiresAt.isBefore(DateTime.now()) ||
        sizeBytes < 1 ||
        sizeBytes > intent.maxBytes ||
        intent.headers['Content-Length'] != '$sizeBytes') {
      throw const FormatException('Upload grant expired or mismatched');
    }
    final client = uploadClient ?? http.Client();
    final request = http.StreamedRequest('PUT', intent.url)
      ..followRedirects = false
      ..contentLength = sizeBytes
      ..headers.addAll(intent.headers);
    try {
      final responseFuture =
          client.send(request).timeout(const Duration(minutes: 3));
      var sent = 0;
      final counted = onProgress == null
          ? bytes
          : bytes.map((chunk) {
              sent += chunk.length;
              onProgress(sent);
              return chunk;
            });
      await request.sink.addStream(counted).timeout(const Duration(minutes: 3));
      await request.sink.close();
      final response = await responseFuture;
      await response.stream.drain<void>();
      if (![200, 201, 204, 412].contains(response.statusCode)) {
        throw ApiFailure(
            response.statusCode, 'The video upload failed. Try again.');
      }
    } on TimeoutException {
      throw const ApiFailure(503, 'The video upload timed out. Try again.');
    } on http.ClientException {
      throw const ApiFailure(
          503, 'The video upload was interrupted. Try again.');
    } finally {
      if (uploadClient == null) client.close();
    }
  }

  Future<VideoUploadStatus> uploadStatus(String videoId) async {
    if (!isApiId(videoId)) throw const FormatException('Invalid video');
    final result =
        await account.authenticatedRequest('/videos/$videoId/upload-status');
    return VideoUploadStatus.fromJson(result, videoId);
  }

  Future<VideoUploadStatus> completeUpload(String videoId) async {
    if (!isApiId(videoId)) throw const FormatException('Invalid video');
    final result = await account
        .authenticatedRequest('/videos/$videoId/upload-status', method: 'POST');
    return VideoUploadStatus.fromJson(result, videoId);
  }

  /// [state] is one of the service's library filters; `all` sends none.
  Future<OwnedVideoPage> library({String? cursor, String state = 'all'}) async {
    if (cursor != null && !isApiId(cursor)) {
      throw const FormatException('Invalid video cursor');
    }
    if (!const {
      'all',
      'draft',
      'in_progress',
      'review',
      'published',
      'rejected',
      'removed',
      'failed'
    }.contains(state)) {
      throw const FormatException('Invalid library filter');
    }
    final raw =
        await account.authenticatedRequest('/creators/me/videos', query: {
      if (cursor != null) 'cursor': cursor,
      if (state != 'all') 'state': state,
    });
    final entries = raw['items'];
    final next = raw['next_cursor'];
    if (raw.keys.toSet().difference({'items', 'next_cursor'}).isNotEmpty ||
        !raw.containsKey('next_cursor') ||
        entries is! List ||
        entries.length > 20) {
      throw const FormatException('Invalid video library');
    }
    final items = entries.map(OwnedVideo.fromJson).toList(growable: false);
    if (items.map((item) => item.id).toSet().length != items.length ||
        next != null &&
            (next is! String ||
                !isApiId(next) ||
                items.length != 20 ||
                items.last.id != next ||
                next == cursor)) {
      throw const FormatException('Invalid video library page');
    }
    return OwnedVideoPage(items, next as String?);
  }

  Future<OwnedVideo> editDraft(OwnedVideo video,
      {required String title, required String description}) async {
    if (!video.canEditDraft ||
        !isApiId(video.id) ||
        title.trim().isEmpty ||
        title.trim().length > 160 ||
        description.length > 2000) {
      throw const FormatException('Invalid draft metadata');
    }
    final result = OwnedVideo.fromJson(await account.authenticatedRequest(
      '/videos/${video.id}',
      method: 'PATCH',
      body: {'title': title.trim(), 'description': description},
    ));
    if (result.id != video.id ||
        result.creatorId != video.creatorId ||
        !result.canEditDraft) {
      throw const FormatException('Mismatched edited video');
    }
    return result;
  }

  Future<void> deleteDraft(OwnedVideo video) async {
    if (!video.canEditDraft || !isApiId(video.id)) {
      throw const FormatException('Invalid draft deletion');
    }
    final response = await account.authenticatedRequest('/videos/${video.id}',
        method: 'DELETE');
    if (response.length != 2 ||
        response['video_id'] != video.id ||
        response['deleted'] != true) {
      throw const FormatException('Invalid draft deletion response');
    }
  }

  /// The owner's detail read (`GET /creators/me/videos/{id}`), including the moderation revision.
  Future<OwnedVideo> ownedVideo(String videoId) async {
    if (!isApiId(videoId)) throw const FormatException('Invalid video');
    final video = OwnedVideo.fromJson(
        await account.authenticatedRequest('/creators/me/videos/$videoId'));
    if (video.id != videoId) throw const FormatException('Mismatched video');
    return video;
  }

  /// Publish (make public) or unpublish (make private) an approved video. Moderation approval itself is
  /// never granted here: the server answers 409 `review_required` for a video that is not approved.
  Future<OwnedVideo> setVisibility(OwnedVideo video,
      {required bool publish}) async {
    if (!isApiId(video.id) ||
        (publish ? !video.canPublish : !video.canUnpublish)) {
      throw const FormatException('Invalid visibility change');
    }
    final result = OwnedVideo.fromJson(await account.authenticatedRequest(
        '/videos/${video.id}/${publish ? 'publish' : 'unpublish'}',
        method: 'POST'));
    if (result.id != video.id ||
        result.creatorId != video.creatorId ||
        result.state != 'published' ||
        result.visibility != (publish ? 'public' : 'private')) {
      throw const FormatException('Mismatched visibility response');
    }
    return result;
  }

  /// Edit details of a draft, failed, rejected or published video; only the changed fields are sent.
  Future<OwnedVideo> editDetails(OwnedVideo video,
      {String? title,
      String? description,
      String? category,
      List<String>? tags,
      int? coverTimeMs}) async {
    final changes = <String, Object?>{};
    if (title != null && title.trim() != video.title) {
      final cleaned = title.trim();
      if (cleaned.isEmpty || cleaned.length > 160) {
        throw const FormatException('Invalid title');
      }
      changes['title'] = cleaned;
    }
    if (description != null && description != video.description) {
      if (description.length > 2000) {
        throw const FormatException('Invalid description');
      }
      changes['description'] = description;
    }
    if (category != null && category != video.category) {
      if (!videoCategories.containsKey(category)) {
        throw const FormatException('Invalid category');
      }
      changes['category'] = category;
    }
    if (tags != null) {
      final normalized = normalizeTags(tags);
      if (normalized.join(',') != video.tags.join(',')) {
        changes['tags'] = normalized;
      }
    }
    if (coverTimeMs != null && coverTimeMs != video.coverTimeMs) {
      // The service renders the poster at this moment once the video has been
      // processed, so the duration must be known to bound it.
      final duration = video.durationMs;
      if (duration == null ||
          coverTimeMs < 0 ||
          coverTimeMs > 300000 ||
          coverTimeMs > duration) {
        throw const FormatException('Invalid cover moment');
      }
      changes['cover_time_ms'] = coverTimeMs;
    }
    if (!video.canEditDetails || !isApiId(video.id) || changes.isEmpty) {
      throw const FormatException('Invalid video edit');
    }
    final result = OwnedVideo.fromJson(await account.authenticatedRequest(
        '/videos/${video.id}',
        method: 'PATCH',
        body: changes));
    if (result.id != video.id ||
        result.creatorId != video.creatorId ||
        changes.entries.any((entry) => switch (entry.key) {
              'title' => result.title != entry.value,
              'description' => result.description != entry.value,
              'category' => result.category != entry.value,
              'cover_time_ms' => result.coverTimeMs != entry.value,
              _ => result.tags.join(',') != (entry.value as List).join(','),
            })) {
      throw const FormatException('Mismatched edited video');
    }
    return result;
  }

  /// Delete in any state. The server soft-deletes (media is retained under ADR-020).
  Future<void> deleteVideo(OwnedVideo video) async {
    if (!isApiId(video.id)) throw const FormatException('Invalid deletion');
    final response = await account.authenticatedRequest('/videos/${video.id}',
        method: 'DELETE');
    if (response.length != 2 ||
        response['video_id'] != video.id ||
        response['deleted'] != true) {
      throw const FormatException('Invalid deletion response');
    }
  }
}
