import '../../app/screen_route.dart';
import '../shell/mobile_screen.dart';

class VideoFeedScreen extends MobileScreen {
  const VideoFeedScreen({
    super.key,
    required super.catalog,
    required super.dependencies,
    required super.session,
  }) : super(route: const ScreenRoute(24));
}
