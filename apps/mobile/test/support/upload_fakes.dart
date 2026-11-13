import 'dart:async';
import 'dart:typed_data';
import 'package:image_picker/image_picker.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/security/credential_store.dart';
import 'package:kolovibe/features/account/live_account_repository.dart';
import 'package:kolovibe/features/content/live_content_repository.dart';
import 'package:kolovibe/features/creators/live_creator_onboarding_repository.dart';

const accountId = '00000000-0000-4000-8000-000000000001';
const creatorId = '00000000-0000-4000-8000-000000000002';
const videoId = '00000000-0000-4000-8000-000000000003';
const uploadId = '00000000-0000-4000-8000-000000000004';

class UnusedCredentials implements CredentialStore {
  @override
  Future<void> clearRefreshToken() async {}
  @override
  Future<String?> readRefreshToken() async => null;
  @override
  Future<void> writeRefreshToken(String token) async {}
}

LiveAccountRepository unusedAccount() => LiveAccountRepository(
    ApiClient('https://api.example.test/api/v1'), UnusedCredentials());

/// A controllable content service. Mocked: no HTTP, storage or device APIs.
class FakeContent extends LiveContentRepository {
  FakeContent() : super(unusedAccount());

  final events = <String>[];
  final draftKeys = <String>[];
  final uploadKeys = <String>[];
  Map<String, Object?>? lastDraftFields;

  Object? draftError, reserveError, transferError, completeError, statusError;
  Duration grantLife = const Duration(minutes: 5);
  VideoUploadStatus completion = _status('processing');
  final List<Object> statusQueue = [];
  Completer<void>? transferGate;

  static VideoUploadStatus _status(String state,
          {String? reason, bool? retryable}) =>
      VideoUploadStatus(videoId, state,
          failureReason: reason,
          retryable: retryable ??
              ({'draft', 'uploading', 'failed'}.contains(state) ||
                  state == 'processing' && reason != null));

  static VideoUploadStatus status(String state,
          {String? reason, bool? retryable}) =>
      _status(state, reason: reason, retryable: retryable);

  @override
  Future<OwnedVideo> createDraft(
      {required String title,
      required String description,
      required String category,
      List<String> tags = const [],
      required String idempotencyKey}) async {
    events.add('draft');
    draftKeys.add(idempotencyKey);
    lastDraftFields = {
      'title': title,
      'description': description,
      'category': category,
      'tags': normalizeTags(tags),
    };
    if (draftError != null) throw draftError!;
    return OwnedVideo(videoId, creatorId, title.trim(), description, 'draft',
        DateTime.utc(2026, 11, 13),
        category: category, tags: normalizeTags(tags));
  }

  @override
  Future<UploadIntent> reserveUpload(
      OwnedVideo video, int sizeBytes, String idempotencyKey) async {
    events.add('reserve');
    uploadKeys.add(idempotencyKey);
    if (reserveError != null) {
      final error = reserveError!;
      reserveError = null;
      throw error;
    }
    return UploadIntent(
        video.id,
        uploadId,
        Uri.parse('https://media.example.test/upload?signature=opaque'),
        {
          'Content-Type': 'video/mp4',
          'Content-Length': '$sizeBytes',
          'If-None-Match': '*'
        },
        DateTime.now().add(grantLife),
        50 * 1024 * 1024);
  }

  @override
  Future<void> uploadToProvider(
      UploadIntent intent, Stream<List<int>> bytes, int sizeBytes,
      {void Function(int sentBytes)? onProgress}) async {
    events.add('transfer');
    onProgress?.call(sizeBytes ~/ 2);
    await transferGate?.future;
    if (transferError != null) {
      final error = transferError!;
      transferError = null;
      throw error;
    }
    onProgress?.call(sizeBytes);
  }

  @override
  Future<VideoUploadStatus> completeUpload(String videoId) async {
    events.add('complete');
    if (completeError != null) {
      final error = completeError!;
      completeError = null;
      throw error;
    }
    return completion;
  }

  @override
  Future<VideoUploadStatus> uploadStatus(String videoId) async {
    events.add('status');
    if (statusError != null) throw statusError!;
    if (statusQueue.isEmpty) return _status('processing');
    final next = statusQueue.removeAt(0);
    if (next is VideoUploadStatus) return next;
    throw next;
  }
}

class FakeOnboarding extends LiveCreatorOnboardingRepository {
  FakeOnboarding() : super(unusedAccount());

  Object? error;
  bool eligible = true;
  int checks = 0;

  @override
  Future<UploadEligibility> eligibility() async {
    checks++;
    if (error != null) {
      final failure = error!;
      error = null;
      throw failure;
    }
    return UploadEligibility(eligible, eligible ? creatorId : null);
  }
}

/// An in-memory picked file (no device or file-system access).
class MemoryXFile extends XFile {
  MemoryXFile(this._name, this._bytes, {int? reportedSize})
      : _size = reportedSize ?? _bytes.length,
        super('memory://$_name');

  final String _name;
  final Uint8List _bytes;
  final int _size;

  @override
  String get name => _name;

  @override
  Future<int> length() async => _size;

  @override
  Stream<Uint8List> openRead([int? start, int? end]) => Stream.value(
      Uint8List.sublistView(_bytes, start ?? 0, end ?? _bytes.length));
}

XFile mp4({int size = 64, String name = 'story.mp4', int? reportedSize}) {
  final bytes = Uint8List(size < 12 ? 12 : size);
  bytes.setRange(4, 8, [0x66, 0x74, 0x79, 0x70]);
  return MemoryXFile(name, bytes, reportedSize: reportedSize ?? size);
}

/// Right extension and size, but the bytes are not an MP4 container.
XFile notMp4() => MemoryXFile('story.mp4', Uint8List(64));
