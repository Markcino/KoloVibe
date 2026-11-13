import 'dart:async';

import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/features/discovery/live_video_repository.dart';
import 'package:kolovibe/features/moderation/live_moderation_repository.dart';

import 'points_fakes.dart' show entryId;
import 'upload_fakes.dart';

/// Serves one public video. Mocked: no HTTP.
class ScriptedVideos extends LiveVideoRepository {
  ScriptedVideos() : super(ApiClient('https://api.example.test/api/v1'));

  Object? failure;
  int reads = 0;

  @override
  Future<LiveVideo> detail(String id) async {
    reads++;
    final error = failure;
    if (error != null) throw error;
    return LiveVideo(id, creatorId, 'Waterside at dawn', 'A city waking up.');
  }
}

/// One own report, with a deterministic id.
ReportRecord ownReport(int n,
        {String video = videoId,
        String status = 'open',
        String reason = 'copyright'}) =>
    ReportRecord(
        entryId(n), video, status, DateTime.utc(2026, 11, 11, 12), reason);

/// A scripted moderation service. Mocked: no HTTP.
///
/// [reports] is the caller's own list, newest first, paged like the server
/// (the cursor is the last id of the previous page).
class ScriptedModeration extends LiveModerationRepository {
  ScriptedModeration({this.pageSize = 20}) : super(unusedAccount());

  final int pageSize;
  List<ReportRecord> reports = [];
  final submissions =
      <({String videoId, String reason, String details, String key})>[];
  final List<Object> failures = [];
  Object? listFailure;
  Completer<void>? gate;
  int listReads = 0;

  @override
  Future<ModerationReceipt> report(
      {required String videoId,
      required String reason,
      required String details,
      required String key}) async {
    submissions
        .add((videoId: videoId, reason: reason, details: details, key: key));
    final pending = gate;
    if (pending != null) await pending.future;
    if (failures.isNotEmpty) throw failures.removeAt(0);
    return ModerationReceipt(
        entryId(900), videoId, 'open', DateTime.utc(2026, 11, 11, 12));
  }

  @override
  Future<ReportPage> ownReports({String? cursor}) async {
    listReads++;
    final failure = listFailure;
    if (failure != null) throw failure;
    final start =
        cursor == null ? 0 : reports.indexWhere((r) => r.id == cursor) + 1;
    final page = reports.skip(start).take(pageSize).toList();
    final more = start + page.length < reports.length;
    return ReportPage(page, more ? page.last.id : null);
  }
}

const alreadyReported = ApiFailure(
    409, 'You already have an open report for this video.',
    code: 'already_reported');
const offlineReport = ApiFailure(
    503, 'The service is unavailable. Please try again.',
    offline: true);
const expiredReport = ApiFailure(401, 'Session expired');
