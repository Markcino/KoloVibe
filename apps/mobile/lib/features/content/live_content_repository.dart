import 'dart:async';
import 'package:http/http.dart' as http;
import '../../core/network/api_client.dart';
import '../account/live_account_repository.dart';

class OwnedVideo {
  const OwnedVideo(this.id, this.creatorId, this.title, this.description,
      this.state, this.createdAt);

  final String id, creatorId, title, description, state;
  final DateTime createdAt;

  bool get canEditDraft => state == 'draft';

  factory OwnedVideo.fromJson(Object? raw) {
    if (raw is! Map<String, dynamic> ||
        raw.keys.toSet().difference({
          'id',
          'creator_id',
          'title',
          'description',
          'state',
          'created_at'
        }).isNotEmpty) {
      throw const FormatException('Invalid owned video');
    }
    final id = raw['id'];
    final creatorId = raw['creator_id'];
    final title = raw['title'];
    final description = raw['description'];
    final state = raw['state'];
    final createdAt = raw['created_at'];
    const states = {
      'draft',
      'uploading',
      'processing',
      'failed',
      'review',
      'published',
      'rejected',
      'removed'
    };
    if (!isApiId(id) ||
        !isApiId(creatorId) ||
        title is! String ||
        title.isEmpty ||
        title.length > 160 ||
        description is! String ||
        description.length > 2000 ||
        state is! String ||
        !states.contains(state) ||
        createdAt is! String) {
      throw const FormatException('Invalid owned video');
    }
    final timestamp = DateTime.tryParse(createdAt);
    if (timestamp == null ||
        !createdAt.contains(RegExp(r'(Z|[+-]\d\d:\d\d)$'))) {
      throw const FormatException('Invalid video timestamp');
    }
    return OwnedVideo(id as String, creatorId as String, title, description,
        state, timestamp);
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

class VideoUploadStatus {
  const VideoUploadStatus(this.videoId, this.state);
  final String videoId, state;

  factory VideoUploadStatus.fromJson(
      Map<String, dynamic> data, String videoId) {
    if (data.keys.toSet().difference({'video_id', 'state'}).isNotEmpty ||
        data['video_id'] != videoId ||
        !{
          'draft',
          'uploading',
          'processing',
          'failed',
          'review',
          'published',
          'rejected',
          'removed'
        }.contains(data['state'])) {
      throw const FormatException('Invalid upload status');
    }
    return VideoUploadStatus(videoId, data['state'] as String);
  }
}

class LiveContentRepository {
  const LiveContentRepository(this.account, {this.uploadClient});

  final LiveAccountRepository account;
  final http.Client? uploadClient;

  Future<OwnedVideo> createDraft(
      {required String title,
      required String description,
      required String idempotencyKey}) async {
    final cleaned = title.trim();
    if (cleaned.isEmpty || cleaned.length > 160 || description.length > 2000) {
      throw const FormatException('Invalid draft metadata');
    }
    final result = OwnedVideo.fromJson(await account.authenticatedRequest(
        '/videos',
        method: 'POST',
        idempotencyKey: idempotencyKey,
        body: {'title': cleaned, 'description': description}));
    if (!result.canEditDraft) {
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
      UploadIntent intent, Stream<List<int>> bytes, int sizeBytes) async {
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
      await request.sink.addStream(bytes).timeout(const Duration(minutes: 3));
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

  Future<OwnedVideoPage> library({String? cursor}) async {
    if (cursor != null && !isApiId(cursor)) {
      throw const FormatException('Invalid video cursor');
    }
    final raw = await account.authenticatedRequest('/creators/me/videos',
        query: {if (cursor != null) 'cursor': cursor});
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
}
