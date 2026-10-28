import '../../app/screen_route.dart';
import '../shell/mobile_screen.dart';

class ExploreScreen extends MobileScreen {
  const ExploreScreen({
    super.key,
    required super.catalog,
    required super.dependencies,
    required super.session,
  }) : super(route: const ScreenRoute(19));
}
