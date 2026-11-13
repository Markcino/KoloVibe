import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/app/routes/trust_routes.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/features/content/live_content_repository.dart';
import 'package:kolovibe/features/moderation/standing_controller.dart';
import 'package:kolovibe/shared/state/async_resource.dart';

import 'support/standing_fakes.dart';
import 'support/upload_fakes.dart';

/// Controller tests with scripted (fake) services. No HTTP.
void main() {
  late ScriptedStanding service;
  setUp(() => service = ScriptedStanding());

  group('AsyncResource', () {
    test('loads, then fails with a retry', () async {
      final resource = AsyncResource<int>(() async => 7);
      expect(resource.phase, ResourcePhase.loading);
      await resource.load();
      expect(resource.value, 7);
      var fail = true;
      final flaky = AsyncResource<int>(() async {
        if (fail) throw const ApiFailure(503, 'down', offline: true);
        return 1;
      });
      await flaky.load();
      expect(flaky.phase, ResourcePhase.failed);
      expect((flaky.error as ApiFailure).kind, FailureKind.offline);
      fail = false;
      await flaky.load();
      expect(flaky.phase, ResourcePhase.ready);
      expect(flaky.error, isNull);
    });

    test('an unreadable response is a failure with fixed text', () async {
      final resource = AsyncResource<int>(
          () async => throw const FormatException('x'),
          unreadable: 'Could not read it.');
      await resource.load();
      expect(resource.phase, ResourcePhase.failed);
      expect((resource.error as ApiFailure).message, 'Could not read it.');
      expect(resource.value, isNull);
    });

    test('a slow old load cannot overwrite a newer one', () async {
      final gates = [Completer<int>(), Completer<int>()];
      var call = 0;
      final resource = AsyncResource<int>(() => gates[call++].future);
      final first = resource.load();
      final second = resource.load();
      gates[1].complete(2);
      await second;
      gates[0].complete(1);
      await first;
      expect(resource.value, 2);
    });

    test('a load that finishes after dispose does nothing', () async {
      final gate = Completer<int>();
      final resource = AsyncResource<int>(() => gate.future);
      final pending = resource.load();
      resource.dispose();
      gate.complete(1);
      await pending;
      expect(resource.value, isNull);
    });
  });

  group('StandingController', () {
    test('loads standing and the titles of noticed videos', () async {
      service.standingValue = standingWith([videoId, videoIdFor(1)]);
      Set<String>? asked;
      final controller = StandingController(service, titleLookup: (ids) async {
        asked = ids;
        return {videoId: 'Waterside at dawn', videoIdFor(9): 'Not noticed'};
      });
      await controller.load();
      expect(asked, {videoId, videoIdFor(1)});
      // Only titles for noticed videos are kept; a missing one stays unnamed.
      expect(controller.titles, {videoId: 'Waterside at dawn'});
    });

    test('a title failure never fails standing', () async {
      service.standingValue = standingWith([videoId]);
      final controller = StandingController(service,
          titleLookup: (_) async => throw const ApiFailure(503, 'down'));
      await controller.load();
      expect(controller.standing.phase, ResourcePhase.ready);
      expect(controller.titles, isEmpty);
    });

    test('no lookup is made without notices or after a failure', () async {
      var lookups = 0;
      final controller = StandingController(service, titleLookup: (_) async {
        lookups++;
        return {};
      });
      await controller.load();
      service.standingFailure = const ApiFailure(503, 'down');
      await controller.load();
      expect(lookups, 0);
      expect(controller.standing.phase, ResourcePhase.failed);
    });
  });

  group('ownVideoTitles', () {
    test('pages the own library, stops when every id is found', () async {
      final content = _Library([
        for (var n = 1; n <= 5; n++) _video(n),
      ], pageSize: 2);
      final titles =
          await ownVideoTitles(content, {videoIdFor(1), videoIdFor(3)});
      expect(titles, {videoIdFor(1): 'Video 1', videoIdFor(3): 'Video 3'});
      expect(content.reads, 2); // page 3 was not needed
    });

    test('is bounded and leaves unknown ids out', () async {
      final content =
          _Library([for (var n = 1; n <= 20; n++) _video(n)], pageSize: 1);
      final titles = await ownVideoTitles(content, {videoIdFor(99)});
      expect(titles, isEmpty);
      expect(content.reads, 5);
    });
  });
}

OwnedVideo _video(int n) => OwnedVideo(videoIdFor(n), creatorId, 'Video $n', '',
    'removed', DateTime.utc(2026, 11, 11));

class _Library extends LiveContentRepository {
  _Library(this.videos, {required this.pageSize}) : super(unusedAccount());
  final List<OwnedVideo> videos;
  final int pageSize;
  int reads = 0;

  @override
  Future<OwnedVideoPage> library({String? cursor}) async {
    reads++;
    final start =
        cursor == null ? 0 : videos.indexWhere((v) => v.id == cursor) + 1;
    final page = videos.skip(start).take(pageSize).toList();
    final more = start + page.length < videos.length;
    return OwnedVideoPage(page, more ? page.last.id : null);
  }
}
