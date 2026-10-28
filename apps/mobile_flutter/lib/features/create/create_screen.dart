import '../../app/screen_route.dart';
import '../shell/mobile_screen.dart';

class CreateScreen extends MobileScreen {
  const CreateScreen({
    super.key,
    required super.catalog,
    required super.dependencies,
    required super.session,
  }) : super(route: const ScreenRoute(37));
}
