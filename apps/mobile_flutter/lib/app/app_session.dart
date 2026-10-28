import 'package:flutter/foundation.dart';

/// Transient preview state. This never represents a server authentication claim.
class AppSession extends ChangeNotifier {
  bool viewerPreview = false;
  int? returnTo;
  String? reportReason;
  bool liked = false, following = false;
  void expire({int destination = 37}) {
    returnTo = destination;
    notifyListeners();
  }

  void clear() {
    returnTo = null;
    liked = false;
    following = false;
    reportReason = null;
    notifyListeners();
  }
}
