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
}
