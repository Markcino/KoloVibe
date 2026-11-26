import '../core/network/api_client.dart';
import '../features/business/business_screens.dart';

/// Typed arguments accepted by the application Navigator.
class ScreenRoute {
  const ScreenRoute(this.screen, {this.entityId, this.returnTo});
  final int screen;
  final String? entityId;
  final int? returnTo;

  /// M-001 to M-108 are the designed creator-content screens; M-109 onward are the Business screens.
  bool get valid => screen >= 1 && screen <= BusinessScreens.last;
  bool get isBusiness => BusinessScreens.contains(screen);
  String get name => '/mobile/M-${screen.toString().padLeft(3, '0')}';

  /// Owner decision SIM-02: a shared video link (`/open/videos/<id>`) that the
  /// operating system opened in the app (iOS Universal Links, Android App
  /// Links) becomes the video detail screen. Only the path is read; any other
  /// location is not a link this app claims. The video itself is read through
  /// the normal API, so the server still decides whether it may be shown.
  static ScreenRoute? fromAppLink(String? location) {
    if (location == null || location.length > 2048) return null;
    final uri = Uri.tryParse(location);
    final match = uri == null
        ? null
        : RegExp(r'^/open/videos/([^/]+)/?$').firstMatch(uri.path);
    final id = match?.group(1);
    return isApiId(id) ? ScreenRoute(25, entityId: id!.toLowerCase()) : null;
  }
}
