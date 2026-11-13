import 'dart:async';

import 'package:kolovibe/features/moderation/live_standing_repository.dart';

import 'upload_fakes.dart';

String videoIdFor(int n) =>
    '00000000-0000-4000-8000-${(0x300000 + n).toRadixString(16).padLeft(12, '0')}';

OwnAppeal ownAppeal(
        {String status = 'open',
        String reason = 'The audio is licensed to me.'}) =>
    OwnAppeal('00000000-0000-4000-8000-000000000a01', status,
        DateTime.utc(2026, 11, 2), reason);

VideoNotice videoNotice(
        {String video = videoId,
        String decision = 'removed',
        String? code = 'REVIEWED_REMOVE',
        bool appealable = false,
        OwnAppeal? appeal}) =>
    VideoNotice(
        video,
        decision,
        decision == 'none' ? null : code,
        decision == 'none' ? null : DateTime.utc(2026, 10, 28, 12),
        appealable,
        appeal);

/// A scripted moderation-notice service. Mocked: no HTTP.
class ScriptedStanding extends LiveStandingRepository {
  ScriptedStanding() : super(unusedAccount());

  VideoNotice? noticeValue;
  AccountStanding standingValue = const AccountStanding('active', true, []);
  Object? noticeFailure, standingFailure;
  final noticeReads = <String>[];
  int standingReads = 0;
  Completer<void>? gate;

  @override
  Future<VideoNotice> notice(String id) async {
    noticeReads.add(id);
    final pending = gate;
    if (pending != null) await pending.future;
    final failure = noticeFailure;
    if (failure != null) throw failure;
    return noticeValue ?? videoNotice(video: id);
  }

  @override
  Future<AccountStanding> standing() async {
    standingReads++;
    final failure = standingFailure;
    if (failure != null) throw failure;
    return standingValue;
  }
}

/// An active, publishing creator with one removal notice per id.
AccountStanding standingWith(List<String> ids) => AccountStanding(
    'active', true, [for (final id in ids) videoNotice(video: id)]);
