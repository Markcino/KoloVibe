import 'package:flutter/foundation.dart';

/// Transient navigation state. This never represents a server authentication claim.
class AppSession extends ChangeNotifier {
  int? returnTo;
  String? reportReason;
  void expire({int destination = 37}) {
    returnTo = destination;
    notifyListeners();
  }

  void clear() {
    returnTo = null;
    reportReason = null;
    notifyListeners();
  }
}
