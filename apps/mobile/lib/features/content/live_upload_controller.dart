import 'dart:convert';
import 'dart:math';
import 'package:flutter/foundation.dart';
import 'package:image_picker/image_picker.dart';
import '../../core/network/api_client.dart';
import '../creators/live_creator_onboarding_repository.dart';
import 'live_content_repository.dart';

class LiveUploadController extends ChangeNotifier {
  LiveUploadController(this.content, this.onboarding);

  final LiveContentRepository content;
  final LiveCreatorOnboardingRepository onboarding;
  UploadEligibility? eligibility;
  XFile? selected;
  int? selectedBytes;
  OwnedVideo? draft;
  VideoUploadStatus? status;
  String? error;
  bool busy = false;
  bool _disposed = false;
  String? _draftKey;
  String? _uploadKey;

  void _update() {
    if (!_disposed) notifyListeners();
  }

  String _key() {
    final random = Random.secure();
    return base64Url.encode(List<int>.generate(24, (_) => random.nextInt(256)));
  }

  Future<void> checkEligibility() async {
    if (busy) return;
    busy = true;
    error = null;
    _update();
    try {
      eligibility = await onboarding.eligibility();
    } on ApiFailure catch (failure) {
      error = failure.message;
    } on FormatException {
      error = 'Creator eligibility could not be read.';
    } finally {
      busy = false;
      _update();
    }
  }

  Future<void> select(XFile file) async {
    if (busy) return;
    error = null;
    selected = null;
    selectedBytes = null;
    _update();
    try {
      final size = await file.length();
      if (!file.name.toLowerCase().endsWith('.mp4') ||
          size < 12 ||
          size > 50 * 1024 * 1024) {
        throw const FormatException('Select an MP4 video under 50 MB.');
      }
      final header = await file
          .openRead(0, 12)
          .fold<List<int>>(<int>[], (bytes, chunk) => bytes..addAll(chunk));
      if (header.length < 12 ||
          header[4] != 0x66 ||
          header[5] != 0x74 ||
          header[6] != 0x79 ||
          header[7] != 0x70) {
        throw const FormatException('The selected file is not an MP4 video.');
      }
      selected = file;
      selectedBytes = size;
      _draftKey = _key();
      _uploadKey = _key();
      draft = null;
      status = null;
    } on FormatException catch (failure) {
      error = failure.message;
    } catch (_) {
      error = 'The selected video could not be read.';
    } finally {
      _update();
    }
  }

  Future<void> submit(String title, String description) async {
    if (busy || selected == null || selectedBytes == null) return;
    if (eligibility?.eligible != true) {
      error = 'Creator upload is not available for this account.';
      _update();
      return;
    }
    busy = true;
    error = null;
    _update();
    try {
      draft ??= await content.createDraft(
          title: title, description: description, idempotencyKey: _draftKey!);
      final intent =
          await content.reserveUpload(draft!, selectedBytes!, _uploadKey!);
      await content.uploadToProvider(
          intent, selected!.openRead(), selectedBytes!);
      status = await content.completeUpload(draft!.id);
    } on ApiFailure catch (failure) {
      error = failure.message;
    } on FormatException catch (failure) {
      error = failure.message;
    } catch (_) {
      error = 'The upload was interrupted. Try again.';
    } finally {
      busy = false;
      _update();
    }
  }

  @override
  void dispose() {
    _disposed = true;
    selected = null;
    _draftKey = null;
    _uploadKey = null;
    super.dispose();
  }
}
