import '../../app/screen_route.dart';
import '../shell/mobile_screen.dart';

class ProfileScreen extends MobileScreen {
  const ProfileScreen({
    super.key,
    required super.catalog,
    required super.dependencies,
    required super.session,
  }) : super(route: const ScreenRoute(79));
}
