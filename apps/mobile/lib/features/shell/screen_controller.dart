import 'package:flutter/foundation.dart';
import '../../core/presentation/feature_repository.dart';

/// Owns only transient presentation state; authoritative decisions belong to services.
class ScreenController extends ChangeNotifier {
  ScreenController(this.repository);
  final FeatureRepository repository;
  final Map<String, String> fields = {};
  bool busy = false, dirty = false, acknowledged = false;
  String? error;
  String selected = '', reason = '';
  bool _disposed = false;
  final Set<VoidCallback> sensitiveClearers = {};

  void update(String key, String value) {
    fields[key] = value;
    dirty = true;
  }

  void choose(String value, {bool report = false}) {
    if (report) {
      reason = value;
    } else {
      selected = value;
    }
    notifyListeners();
  }

  void acknowledge(bool value) {
    acknowledged = value;
    notifyListeners();
  }

  Future<UiResult?> submit(UiOperation operation) async {
    if (busy) return null;
    busy = true;
    error = null;
    notifyListeners();
    try {
      final result = await repository.execute(
        UiRequest(
          operation,
          fields: Map.unmodifiable({
            ...fields,
            if (reason.isNotEmpty) 'reason': reason,
          }),
        ),
      );
      if (_disposed) return null;
      if (!result.available) {
        error = result.message;
      } else {
        dirty = false;
      }
      return result;
    } catch (_) {
      if (!_disposed) {
        error = 'The request could not be completed. Please try again.';
      }
      return null;
    } finally {
      fields.removeWhere((key, _) => isSensitiveField(key));
      for (final clear in sensitiveClearers.toList()) {
        clear();
      }
      if (!_disposed) {
        busy = false;
        notifyListeners();
      }
    }
  }

  static bool isSensitiveField(String key) =>
      key.toLowerCase().contains('password') ||
      key.toLowerCase().contains('code') ||
      key.toLowerCase().contains('token');

  @override
  void dispose() {
    _disposed = true;
    fields.clear();
    sensitiveClearers.clear();
    super.dispose();
  }
}
