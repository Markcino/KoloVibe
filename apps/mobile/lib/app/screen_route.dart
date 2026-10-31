/// Typed arguments accepted by the application Navigator.
class ScreenRoute {
  const ScreenRoute(this.screen, {this.entityId, this.returnTo});
  final int screen;
  final String? entityId;
  final int? returnTo;
  bool get valid => screen >= 1 && screen <= 108;
  String get name => '/mobile/M-${screen.toString().padLeft(3, '0')}';
}
