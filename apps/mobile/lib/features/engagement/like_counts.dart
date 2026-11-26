import 'package:flutter/foundation.dart';

/// SIM-04: the like count the server confirmed most recently, shared by every
/// route in this app session.
///
/// A like or unlike answer carries the video's new count. Lists loaded before
/// it would otherwise keep showing the older count until they reload. Every
/// value here is a count the server returned; nothing is counted locally. A
/// newer video page from the server supersedes it, so the freshest server
/// answer always wins. It is memory only and is never stored on the device.
class LikeCounts extends ChangeNotifier {
  LikeCounts._();
  static final shared = LikeCounts._();

  final Map<String, int?> _confirmed = {};

  /// The count to show for [videoId], given the count its list returned.
  int? current(String videoId, int? listed) =>
      _confirmed.containsKey(videoId) ? _confirmed[videoId] : listed;

  /// A like or unlike answer from the server.
  void confirm(String videoId, int? count) {
    if (_confirmed.containsKey(videoId) && _confirmed[videoId] == count) {
      return;
    }
    _confirmed[videoId] = count;
    notifyListeners();
  }

  /// A video page fetched from the server is at least as new as any earlier
  /// confirmation for the same videos.
  void supersede(Iterable<String> videoIds) {
    var changed = false;
    for (final id in videoIds) {
      changed = _confirmed.remove(id) != null || changed;
    }
    if (changed) notifyListeners();
  }

  @visibleForTesting
  void reset() => _confirmed.clear();
}
