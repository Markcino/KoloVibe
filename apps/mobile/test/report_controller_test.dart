import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/features/moderation/report_controller.dart';

import 'support/report_fakes.dart';
import 'support/upload_fakes.dart';

/// Controller tests with scripted (fake) services. No HTTP.
void main() {
  late ScriptedVideos videos;
  late ScriptedModeration moderation;
  var keys = 0;

  setUp(() {
    videos = ScriptedVideos();
    moderation = ScriptedModeration();
    keys = 0;
  });

  ReportController make({ReportLookup lookup = ReportLookup.none}) =>
      ReportController(videos, moderation, videoId,
          lookup: lookup, newKey: () => 'key-${++keys}-abcdefghijkl');

  Future<ReportController> atDetails({String text = ''}) async {
    final controller = make();
    await controller.load();
    controller
      ..choose(reportReasons[3]) // Rights or ownership concern
      ..toDetails()
      ..setDetails(text);
    return controller;
  }

  group('the flow', () {
    test('starts on the reason step and sends nothing', () async {
      final controller = make();
      await controller.load();
      expect(controller.phase, ReportPhase.ready);
      expect(controller.stage, ReportStage.reason);
      expect(controller.canContinue, isFalse);
      controller.toDetails(); // no reason yet: ignored
      expect(controller.stage, ReportStage.reason);
      expect(moderation.submissions, isEmpty);
    });

    test('a reason is required, then details are optional', () async {
      final controller = await atDetails();
      expect(controller.stage, ReportStage.details);
      await controller.submit();
      expect(moderation.submissions.single.reason, 'copyright');
      expect(moderation.submissions.single.details, '');
      expect(controller.stage, ReportStage.submitted);
      expect(controller.receipt!.status, 'open');
    });

    test('details are trimmed and cleared once sent', () async {
      final controller = await atDetails(text: '  audio is not licensed  ');
      await controller.submit();
      expect(moderation.submissions.single.details, 'audio is not licensed');
      expect(controller.details, isEmpty);
    });

    test('two labels that share a server code both send it', () async {
      for (final option in [reportReasons[1], reportReasons[2]]) {
        final controller = make();
        await controller.load();
        controller
          ..choose(option)
          ..toDetails();
        await controller.submit();
        expect(moderation.submissions.last.reason, 'harmful');
      }
    });

    test('a video that is gone is a not-found load failure', () async {
      videos.failure = const ApiFailure(404, 'Not found');
      final controller = make();
      await controller.load();
      expect(controller.phase, ReportPhase.failed);
      expect((controller.loadError as ApiFailure).kind, FailureKind.notFound);
    });
  });

  group('submission', () {
    test('only one request is in flight', () async {
      final controller = await atDetails();
      final gate = moderation.gate = Completer<void>();
      final first = controller.submit();
      final second = controller.submit();
      expect(controller.submitting, isTrue);
      gate.complete();
      await Future.wait([first, second]);
      expect(moderation.submissions, hasLength(1));
    });

    test('an unconfirmed report keeps the text and retries with the same key',
        () async {
      final controller = await atDetails(text: 'keep me');
      moderation.failures.add(offlineReport);
      await controller.submit();
      expect(controller.stage, ReportStage.error);
      expect(controller.details, 'keep me');
      await controller.submit(); // "Try submitting again"
      expect(controller.stage, ReportStage.submitted);
      expect(moderation.submissions.map((s) => s.key).toSet(), hasLength(1));
      expect(moderation.submissions.map((s) => s.details).toSet(), {'keep me'});
    });

    test('changing the reason or text after a failure uses a new key',
        () async {
      final controller = await atDetails(text: 'first');
      moderation.failures.add(offlineReport);
      await controller.submit();
      controller
        ..backToDetails()
        ..setDetails('second');
      await controller.submit();
      expect(moderation.submissions.map((s) => s.key).toSet(), hasLength(2));
    });

    test('an unreadable response is "not confirmed", never "sent"', () async {
      final controller = await atDetails();
      moderation.failures.add(const FormatException('bad'));
      await controller.submit();
      expect(controller.stage, ReportStage.error);
      expect(controller.receipt, isNull);
      expect((controller.submitFailure as ApiFailure).status, 503);
    });

    test('an already-open report becomes M-075 and finds its reason', () async {
      moderation.reports = [ownReport(1, reason: 'copyright')];
      final controller = await atDetails(text: 'again');
      moderation.failures.add(alreadyReported);
      await controller.submit();
      expect(controller.stage, ReportStage.alreadyReported);
      expect(controller.existing!.reason, 'copyright');
      expect(controller.receipt, isNull);
      expect(controller.details, isEmpty);
    });

    test('M-075 still shows when the earlier report cannot be listed',
        () async {
      moderation.listFailure = offlineReport;
      final controller = await atDetails();
      moderation.failures.add(alreadyReported);
      await controller.submit();
      expect(controller.stage, ReportStage.alreadyReported);
      expect(controller.existing, isNull);
    });

    test('a plain 409 is a conflict and forces a new key', () async {
      final controller = await atDetails();
      moderation.failures.add(const ApiFailure(409, 'Idempotency conflict'));
      await controller.submit();
      expect(controller.stage, ReportStage.error);
      await controller.submit();
      expect(moderation.submissions.map((s) => s.key).toSet(), hasLength(2));
    });

    test('an expired session or refusal is not retried automatically',
        () async {
      for (final failure in [
        const ApiFailure(401, 'Session expired'),
        const ApiFailure(403, 'Forbidden'),
        const ApiFailure(404, 'Not found'),
      ]) {
        final controller = await atDetails();
        moderation.failures.add(failure);
        await controller.submit();
        expect(controller.stage, ReportStage.error);
        expect(controller.receipt, isNull);
        expect(controller.submitFailure, same(failure));
      }
    });

    test('back and cancel keep the choices until the report is sent', () async {
      final controller = await atDetails(text: 'draft');
      controller.backToReason();
      expect(controller.stage, ReportStage.reason);
      expect(controller.reason, reportReasons[3]);
      controller.toDetails();
      expect(controller.details, 'draft');
    });
  });

  group('cold entries', () {
    test('M-073 shows the latest report for the video, whatever its state',
        () async {
      moderation.reports = [
        ownReport(1, video: entryIdFor(70)),
        ownReport(2, status: 'resolved', reason: 'spam'),
      ];
      final controller = make(lookup: ReportLookup.latest);
      await controller.load();
      expect(controller.stage, ReportStage.submitted);
      expect(controller.existing!.reason, 'spam');
    });

    test('M-073 with no report falls back to choosing a reason', () async {
      final controller = make(lookup: ReportLookup.latest);
      await controller.load();
      expect(controller.stage, ReportStage.reason);
      expect(controller.existing, isNull);
    });

    test('M-075 needs an open report; a decided one does not count', () async {
      moderation.reports = [ownReport(1, status: 'dismissed')];
      final controller = make(lookup: ReportLookup.openOnly);
      await controller.load();
      expect(controller.stage, ReportStage.reason);
    });

    test('M-075 with an open report shows it', () async {
      moderation.reports = [ownReport(1)];
      final controller = make(lookup: ReportLookup.openOnly);
      await controller.load();
      expect(controller.stage, ReportStage.alreadyReported);
    });

    test('a lookup failure is a retryable load failure', () async {
      moderation.listFailure = offlineReport;
      final controller = make(lookup: ReportLookup.openOnly);
      await controller.load();
      expect(controller.phase, ReportPhase.failed);
      moderation.listFailure = null;
      moderation.reports = [ownReport(1)];
      await controller.load();
      expect(controller.stage, ReportStage.alreadyReported);
    });
  });
}

/// A video id other than [videoId].
String entryIdFor(int n) =>
    '00000000-0000-4000-8000-${(0x200000 + n).toRadixString(16).padLeft(12, '0')}';
