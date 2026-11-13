import 'package:flutter/foundation.dart';
import '../../core/network/api_client.dart';

enum ResourcePhase { loading, failed, ready }

/// Loads one value and exposes loading, failed and ready states.
///
/// A response that cannot be parsed is a failure with [unreadable] text, never
/// partial data. A newer [load] discards an older, slower one.
class AsyncResource<T> extends ChangeNotifier {
  AsyncResource(this._loader,
      {this.unreadable = 'The response could not be read. Try again.'});

  final Future<T> Function() _loader;
  final String unreadable;

  ResourcePhase phase = ResourcePhase.loading;
  Object? error;
  T? value;
  int _generation = 0;
  bool _disposed = false;

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }

  void _emit() {
    if (!_disposed) notifyListeners();
  }

  Future<void> load() async {
    final generation = ++_generation;
    phase = ResourcePhase.loading;
    error = null;
    _emit();
    try {
      final result = await _loader();
      if (_disposed || generation != _generation) return;
      value = result;
      phase = ResourcePhase.ready;
    } on ApiFailure catch (failure) {
      if (_disposed || generation != _generation) return;
      error = failure;
      phase = ResourcePhase.failed;
    } on FormatException {
      if (_disposed || generation != _generation) return;
      error = ApiFailure(503, unreadable);
      phase = ResourcePhase.failed;
    }
    _emit();
  }
}
