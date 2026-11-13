import 'package:flutter/foundation.dart';
import '../../shared/state/async_resource.dart';
import 'live_standing_repository.dart';

/// Loads standing (M-077) and, best effort, the titles of the noticed videos.
///
/// A title is a convenience: any failure leaves the notice unnamed, never
/// invented.
class StandingController extends ChangeNotifier {
  StandingController(LiveStandingRepository repository, {this.titleLookup})
      : standing = AsyncResource<AccountStanding>(repository.standing,
            unreadable: 'Your account status could not be read. Try again.') {
    standing.addListener(notifyListeners);
  }

  final AsyncResource<AccountStanding> standing;

  /// Resolves video ids to own-library titles; may return fewer than asked.
  final Future<Map<String, String>> Function(Set<String> ids)? titleLookup;

  Map<String, String> titles = const {};
  bool _disposed = false;

  @override
  void dispose() {
    _disposed = true;
    standing.removeListener(notifyListeners);
    standing.dispose();
    super.dispose();
  }

  Future<void> load() async {
    titles = const {};
    await standing.load();
    final lookup = titleLookup;
    final value = standing.value;
    if (_disposed ||
        lookup == null ||
        standing.phase != ResourcePhase.ready ||
        value == null ||
        value.notices.isEmpty) {
      return;
    }
    final wanted = value.notices.map((n) => n.videoId).toSet();
    try {
      final found = await lookup(wanted);
      if (_disposed) return;
      titles = {
        for (final entry in found.entries)
          if (wanted.contains(entry.key)) entry.key: entry.value
      };
      notifyListeners();
    } catch (_) {
      // Notices still show, without titles.
    }
  }
}
