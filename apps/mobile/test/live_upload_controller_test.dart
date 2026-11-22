// Controller tests use a fake content service: no HTTP, storage or device APIs.
import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/features/content/live_upload_controller.dart';
import 'support/upload_fakes.dart';

void main() {
  late FakeContent content;
  late FakeOnboarding onboarding;
  late LiveUploadController controller;
  final delays = <Duration>[];

  LiveUploadController build({int maxPolls = 18, UploadDelay? delay}) =>
      LiveUploadController(content, onboarding,
          delay: delay ?? (d) async => delays.add(d), maxPolls: maxPolls);

  Future<void> ready() async {
    await controller.checkEligibility();
    await controller.select(mp4());
  }

  Future<void> submit() {
    controller.originalityAccepted = true;
    return controller.submit(
        '  My original ', 'A story', 'culture', '#Monrovia art, ART');
  }

  setUp(() {
    content = FakeContent();
    onboarding = FakeOnboarding();
    controller = build();
    delays.clear();
  });
  tearDown(() => controller.dispose());

  group('access', () {
    test('an approved creator reaches the editing state', () async {
      expect(controller.phase, UploadPhase.checkingAccess);
      await controller.checkEligibility();
      expect(controller.phase, UploadPhase.editing);
    });

    test('an account without approval cannot upload', () async {
      onboarding.eligible = false;
      await controller.checkEligibility();
      expect(controller.phase, UploadPhase.ineligible);
      await controller.select(mp4());
      expect(controller.selected, isNull);
      await submit();
      expect(content.events, isEmpty);
    });

    test('an eligibility outage can be retried', () async {
      onboarding.error = const ApiFailure(503, 'Service unavailable');
      await controller.checkEligibility();
      expect(controller.phase, UploadPhase.accessFailed);
      await controller.checkEligibility();
      expect(controller.phase, UploadPhase.editing);
    });

    test('an expired session is reported as signed out', () async {
      onboarding.error = const ApiFailure(401, 'expired');
      await controller.checkEligibility();
      expect(controller.phase, UploadPhase.signedOut);
    });

    test('a refusal is reported as restricted', () async {
      onboarding.error = const ApiFailure(403, 'forbidden');
      await controller.checkEligibility();
      expect(controller.phase, UploadPhase.restricted);
    });
  });

  group('file check (M-043)', () {
    setUp(() => controller.checkEligibility());

    test('rejects non-MP4 names, oversize and fake headers locally', () async {
      await controller.select(mp4(name: 'story.mov'));
      expect(controller.error, contains('MP4'));
      expect(controller.selected, isNull);
      await controller.select(mp4(size: 4));
      expect(controller.selected, isNull);
      await controller.select(mp4(reportedSize: 50 * 1024 * 1024 + 1));
      expect(controller.error, contains('50 MB'));
      await controller.select(mp4());
      expect(controller.selected, isNotNull);
      expect(controller.error, isNull);
    });

    test('rejects a file whose header is not an MP4', () async {
      await controller.select(notMp4());
      expect(controller.error, 'The selected file is not an MP4 video.');
      expect(controller.selected, isNull);
    });
  });

  group('story details (M-044)', () {
    setUp(() async => ready());

    test('requires explicit originality consent before any upload request',
        () async {
      expect(controller.originalityAccepted, isFalse);
      await controller.submit('My work', '', 'culture', '');
      expect(content.events, isEmpty);
      expect(controller.phase, UploadPhase.editing);
      expect(controller.error, contains('permission'));
    });

    test('blocks the network until title and category are valid', () async {
      await controller.submit('   ', '', null, '');
      expect(controller.detailsErrors.fields.keys,
          containsAll(['title', 'category']));
      expect(controller.phase, UploadPhase.editing);
      expect(content.events, isEmpty);
    });

    test('rejects bad hashtags and more than five', () async {
      await controller.submit('t', '', 'culture', 'not!valid');
      expect(controller.detailsErrors.fields['tags'], isNotNull);
      await controller.submit('t', '', 'culture', '1 2 3 4 5 6');
      expect(controller.detailsErrors.fields['tags'], contains('five'));
      expect(content.events, isEmpty);
    });

    test('limits title and description length', () {
      final errors =
          validateUploadDetails('x' * 161, 'y' * 2001, 'culture', '');
      expect(errors.fields.keys, containsAll(['title', 'description']));
    });
  });

  group('upload (M-046) and preparation (M-049)', () {
    setUp(() async => ready());

    test('creates the draft, reserves, transfers, completes and polls',
        () async {
      content.completion = FakeContent.status('processing');
      content.statusQueue
        ..add(FakeContent.status('processing'))
        ..add(FakeContent.status('review'));
      final progress = <double?>[];
      controller.addListener(() => progress.add(controller.progress));
      await submit();
      await pumpEventQueue();
      expect(
          content.events.take(4), ['draft', 'reserve', 'transfer', 'complete']);
      expect(content.lastDraftFields, {
        'title': 'My original',
        'description': 'A story',
        'category': 'culture',
        'tags': ['monrovia', 'art'],
      });
      expect(progress, contains(0.5));
      expect(controller.phase, UploadPhase.settled);
      expect(controller.status!.state, 'review');
      expect(content.events.where((e) => e == 'status'), hasLength(2));
      expect(delays.first, const Duration(seconds: 3));
    });

    test('shows the preparing state until the server reports an outcome',
        () async {
      final gate = Completer<void>();
      var released = false;
      controller.dispose();
      controller = build(delay: (_) async {
        if (!released) await gate.future;
      });
      await ready();
      await submit();
      expect(controller.phase, UploadPhase.preparing);
      released = true;
      content.statusQueue.add(FakeContent.status('published'));
      gate.complete();
      await pumpEventQueue();
      expect(controller.phase, UploadPhase.settled);
      expect(controller.status!.state, 'published');
    });

    test('stops polling after the bound and allows a manual refresh', () async {
      controller.dispose();
      controller = build(maxPolls: 3);
      await ready();
      await submit();
      await pumpEventQueue();
      expect(content.events.where((e) => e == 'status'), hasLength(3));
      expect(controller.phase, UploadPhase.preparing);
      expect(controller.stalePreparation, isTrue);
      content.statusQueue.add(FakeContent.status('review'));
      await controller.refreshStatus();
      expect(controller.phase, UploadPhase.settled);
      expect(controller.stalePreparation, isFalse);
    });

    test('repeated status failures stop polling without losing the video',
        () async {
      content.statusError = const ApiFailure(503, 'down', offline: true);
      await submit();
      await pumpEventQueue();
      expect(content.events.where((e) => e == 'status'), hasLength(3));
      expect(controller.stalePreparation, isTrue);
      expect(controller.phase, UploadPhase.preparing);
    });

    test('a session that ends while preparing is surfaced', () async {
      content.statusQueue.add(const ApiFailure(401, 'expired'));
      await submit();
      await pumpEventQueue();
      expect(controller.phase, UploadPhase.signedOut);
    });

    test('disposing stops polling', () async {
      final gate = Completer<void>();
      controller.dispose();
      controller = build(delay: (_) => gate.future);
      await ready();
      await submit();
      controller.dispose();
      gate.complete();
      await pumpEventQueue();
      expect(content.events.where((e) => e == 'status'), isEmpty);
    });

    test('a video that is already in review is settled immediately', () async {
      content.completion = FakeContent.status('review');
      await submit();
      expect(controller.phase, UploadPhase.settled);
      expect(content.events.where((e) => e == 'status'), isEmpty);
    });
  });

  group('interruption (M-047) and idempotency', () {
    setUp(() async => ready());

    test('a dropped transfer resumes with the same reservation key', () async {
      content.transferError = const ApiFailure(503, 'cut', offline: true);
      await submit();
      expect(controller.phase, UploadPhase.interrupted);
      expect(controller.error, contains('offline'));
      expect(controller.draft, isNotNull);
      await controller.retry();
      await pumpEventQueue();
      expect(content.events.where((e) => e == 'draft'), hasLength(1));
      expect(content.uploadKeys.toSet(), hasLength(1));
      expect(content.draftKeys, hasLength(1));
      expect(controller.phase, UploadPhase.preparing);
      expect(content.events.where((e) => e == 'transfer'), hasLength(2));
      expect(content.events.where((e) => e == 'complete'), hasLength(1));
    });

    test('an expired grant is replaced with a fresh key', () async {
      content.grantLife = const Duration(milliseconds: -1);
      content.transferError = const ApiFailure(503, 'cut');
      await submit();
      content.grantLife = const Duration(minutes: 5);
      await controller.retry();
      expect(content.uploadKeys.toSet().length, greaterThan(1));
    });

    test('a conflicting reservation is retried with a fresh key', () async {
      content.reserveError = const ApiFailure(409, 'Reservation replaced');
      await submit();
      expect(controller.phase, UploadPhase.interrupted);
      await controller.retry();
      expect(content.uploadKeys.toSet(), hasLength(2));
      expect(content.events.where((e) => e == 'draft'), hasLength(1));
    });

    test('a completion outage retries only the completion', () async {
      content.completeError = const ApiFailure(503, 'queue down');
      await submit();
      expect(controller.phase, UploadPhase.interrupted);
      await controller.retry();
      expect(content.events.where((e) => e == 'transfer'), hasLength(1));
      expect(content.events.where((e) => e == 'complete'), hasLength(2));
    });

    test('a non-MP4 replacement cannot be chosen after completion', () async {
      content.completeError = const ApiFailure(503, 'queue down');
      await submit();
      expect(controller.canPickFile, isFalse);
    });

    test('rejected story details return to editing', () async {
      content.draftError = const ApiFailure(400, 'Invalid request');
      await submit();
      expect(controller.phase, UploadPhase.editing);
      expect(controller.error, 'Invalid request');
      expect(controller.draft, isNull);
    });

    test('a session that ends mid-upload asks for sign-in', () async {
      content.draftError = const ApiFailure(401, 'expired');
      await submit();
      expect(controller.phase, UploadPhase.signedOut);
    });

    test('a restriction during upload stops without retry', () async {
      content.reserveError = const ApiFailure(403, 'Approved creator required');
      await submit();
      expect(controller.phase, UploadPhase.restricted);
      await controller.retry();
      expect(controller.phase, UploadPhase.restricted);
    });
  });

  group('failure (M-048)', () {
    setUp(() async => ready());

    test('a server-confirmed failure retries with a fresh reservation',
        () async {
      content.completion =
          FakeContent.status('failed', reason: 'upload_missing');
      await submit();
      expect(controller.phase, UploadPhase.failed);
      expect(controller.status!.failureReason, 'upload_missing');
      content.completion = FakeContent.status('processing');
      await controller.retry();
      expect(content.uploadKeys.toSet(), hasLength(2));
      expect(content.events.where((e) => e == 'draft'), hasLength(1));
    });

    test('invalid media cannot be retried with the same file', () async {
      content.completion =
          FakeContent.status('failed', reason: 'invalid_media');
      await submit();
      final before = content.events.length;
      await controller.retry();
      expect(content.events.length, before);
      await controller.select(mp4(name: 'better.mp4'));
      expect(controller.phase, UploadPhase.editing);
      expect(controller.selected!.name, 'better.mp4');
      content.completion = FakeContent.status('processing');
      await submit();
      expect(content.events.where((e) => e == 'draft'), hasLength(1));
      expect(content.uploadKeys.toSet(), hasLength(2));
    });

    test('a transient processing failure retries completion only', () async {
      content.completion =
          FakeContent.status('processing', reason: 'processing_unavailable');
      await submit();
      expect(controller.phase, UploadPhase.preparing);
      content.completion = FakeContent.status('review');
      await controller.retryPreparation();
      expect(controller.phase, UploadPhase.settled);
      expect(content.events.where((e) => e == 'transfer'), hasLength(1));
    });

    test('retryPreparation is ignored when the server did not allow it',
        () async {
      content.completion = FakeContent.status('processing');
      await submit();
      await pumpEventQueue();
      final before = content.events.length;
      await controller.retryPreparation();
      expect(content.events.length, before);
    });
  });
}
