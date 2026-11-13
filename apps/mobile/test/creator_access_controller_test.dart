import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/features/creators/creator_access_controller.dart';
import 'package:kolovibe/features/creators/own_profile_controller.dart';

import 'support/creator_fakes.dart';

/// Controller tests with scripted (fake) repositories. No HTTP.
void main() {
  group('CreatorAccessController', () {
    late ScriptedOnboarding onboarding;
    late CreatorAccessController controller;
    setUp(() {
      onboarding = ScriptedOnboarding();
      controller = CreatorAccessController(onboarding);
    });
    tearDown(() => controller.dispose());

    test('maps real server state to a phase', () async {
      final cases = <(bool, String?, CreatorAccessPhase)>[
        (true, 'approved', CreatorAccessPhase.eligible),
        (false, null, CreatorAccessPhase.noInvitation),
        (false, 'invited', CreatorAccessPhase.invited),
        (false, 'pending', CreatorAccessPhase.pending),
        (false, 'rejected', CreatorAccessPhase.rejected),
        (false, 'approved', CreatorAccessPhase.restricted),
      ];
      for (final (eligible, status, phase) in cases) {
        onboarding
          ..eligible = eligible
          ..status = status;
        await controller.load();
        expect(controller.phase, phase, reason: '$eligible $status');
      }
    });

    test('starts loading and reports offline and expired sessions', () async {
      final future = controller.load();
      expect(controller.phase, CreatorAccessPhase.loading);
      await future;
      onboarding.failures.add(offline);
      await controller.load();
      expect(controller.phase, CreatorAccessPhase.failed);
      expect((controller.error as ApiFailure).kind, FailureKind.offline);
      onboarding.failures.add(expired);
      await controller.load();
      expect((controller.error as ApiFailure).kind, FailureKind.expired);
      await controller.load(); // retry recovers
      expect(controller.phase, CreatorAccessPhase.noInvitation);
      expect(controller.error, isNull);
    });

    test('submission is checked before any request', () async {
      onboarding.status = 'invited';
      await controller.load();
      for (final handle in ['', 'Ama', 'ab', 'ama kollie']) {
        await controller.submit(
            handle: handle, adultAttested: true, rightsAttested: true);
        expect(controller.submitError, isNotNull, reason: handle);
      }
      await controller.submit(
          handle: 'ama', adultAttested: true, rightsAttested: false);
      expect(controller.submitError, 'Confirm both statements to continue.');
      expect(onboarding.submissions, isEmpty);
    });

    test('a valid application is sent once and the status reloads', () async {
      onboarding.status = 'invited';
      await controller.load();
      final first = controller.submit(
          handle: ' ama_k ', adultAttested: true, rightsAttested: true);
      final second = controller.submit(
          handle: 'ama_k', adultAttested: true, rightsAttested: true);
      await Future.wait([first, second]);
      expect(onboarding.submissions, hasLength(1));
      expect(onboarding.submissions.single['handle'], ' ama_k ');
      expect(controller.phase, CreatorAccessPhase.pending);
      expect(controller.submitError, isNull);
      expect(controller.submitting, isFalse);
    });

    test('a handle conflict stays on the form; an expired session does not',
        () async {
      onboarding.status = 'invited';
      await controller.load();
      onboarding.submitFailure =
          const ApiFailure(409, 'Application or handle conflict');
      await controller.submit(
          handle: 'ama_k', adultAttested: true, rightsAttested: true);
      expect(controller.phase, CreatorAccessPhase.invited);
      expect(controller.submitError, contains('Choose another handle'));
      onboarding.submitFailure = expired;
      await controller.submit(
          handle: 'ama_k', adultAttested: true, rightsAttested: true);
      expect(controller.phase, CreatorAccessPhase.failed);
      expect((controller.error as ApiFailure).kind, FailureKind.expired);
    });

    test('submitting outside the invited state is ignored', () async {
      onboarding.status = 'pending';
      await controller.load();
      await controller.submit(
          handle: 'ama_k', adultAttested: true, rightsAttested: true);
      expect(onboarding.submissions, isEmpty);
    });

    test('disposing while a request is in flight is safe', () async {
      final future = controller.load();
      controller.dispose();
      await future;
      controller = CreatorAccessController(onboarding); // for tearDown
    });
  });

  group('OwnProfileController', () {
    late ScriptedOwnCreator profiles;
    late OwnProfileController controller;
    setUp(() {
      profiles = ScriptedOwnCreator();
      controller = OwnProfileController(profiles,
          publicCreators: CountingPublicCreators(12));
    });
    tearDown(() => controller.dispose());

    test('loads the real profile and the published count', () async {
      await controller.load();
      expect(controller.phase, OwnProfilePhase.ready);
      expect(controller.profile!.handle, 'amakollie');
      expect(controller.publishedVideoCount, 12);
    });

    test('a failing public count never blocks the profile', () async {
      final counts = CountingPublicCreators(3)..failure = offline;
      controller = OwnProfileController(profiles, publicCreators: counts);
      await controller.load();
      expect(controller.phase, OwnProfilePhase.ready);
      expect(controller.publishedVideoCount, isNull);
    });

    test('forbidden, missing and offline reads fail with their kind', () async {
      for (final (failure, kind) in [
        (const ApiFailure(403, 'Creator role required'), FailureKind.forbidden),
        (const ApiFailure(404, 'Own profile not found'), FailureKind.notFound),
        (offline, FailureKind.offline),
        (expired, FailureKind.expired),
      ]) {
        profiles.profileFailure = failure;
        await controller.load();
        expect(controller.phase, OwnProfilePhase.failed);
        expect((controller.error as ApiFailure).kind, kind);
      }
      profiles.profileFailure = null;
      await controller.load();
      expect(controller.phase, OwnProfilePhase.ready);
    });

    test('saving sends the edit and keeps the new profile', () async {
      await controller.load();
      final saved = await controller.save(
          displayName: 'Ama K.',
          bio: 'Finding the cinema in the everyday.',
          location: 'Monrovia',
          handle: 'amakollie');
      expect(saved, isTrue);
      expect(controller.profile!.displayName, 'Ama K.');
      expect(profiles.updates, hasLength(1));
    });

    test('an invalid new handle is explained and not sent', () async {
      await controller.load();
      final saved = await controller.save(
          displayName: 'Ama Kollie',
          bio: 'x',
          location: 'Monrovia',
          handle: 'ama kollie');
      expect(saved, isFalse);
      expect(controller.handleError, contains('Spaces'));
      expect(profiles.updates, isEmpty);
    });

    test('a legacy handle that is unchanged is not re-validated', () async {
      profiles.current = ownCreator(handle: 'Ama-K');
      await controller.load();
      expect(
          await controller.save(
              displayName: 'New name',
              bio: profiles.current.bio,
              location: profiles.current.location,
              handle: 'Ama-K'),
          isTrue);
      expect(controller.handleError, isNull);
    });

    test('handle_taken is a field error and keeps the form editable', () async {
      await controller.load();
      profiles.updateFailure =
          const ApiFailure(409, 'unavailable', code: 'handle_taken');
      final saved = await controller.save(
          displayName: 'Ama Kollie',
          bio: profiles.current.bio,
          location: 'Monrovia',
          handle: 'taken_one');
      expect(saved, isFalse);
      expect(controller.handleError, contains('already taken'));
      expect(controller.saveError, isNull);
      expect(controller.saving, isFalse);
    });

    test('offline and expired failures keep the user\'s changes', () async {
      await controller.load();
      for (final failure in [offline, expired]) {
        profiles.updateFailure = failure;
        expect(
            await controller.save(
                displayName: 'Changed',
                bio: profiles.current.bio,
                location: 'Monrovia',
                handle: 'amakollie'),
            isFalse);
        expect(controller.saveError, isNotNull);
        expect(controller.profile!.displayName, 'Ama Kollie');
      }
    });

    test('a restricted creator sees the server reason', () async {
      await controller.load();
      profiles.updateFailure =
          const ApiFailure(403, 'Creator profile unavailable');
      await controller.save(
          displayName: 'Changed',
          bio: profiles.current.bio,
          location: 'Monrovia',
          handle: 'amakollie');
      expect(controller.saveError, 'Creator profile unavailable');
    });
  });
}
