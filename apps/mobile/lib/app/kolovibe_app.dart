import 'package:flutter/material.dart';
import '../core/presentation/design_node.dart';
import '../core/theme/kolovibe_theme.dart';
import '../features/shell/mobile_screen.dart';
import '../features/home/home_screen.dart';
import '../features/explore/explore_screen.dart';
import '../features/create/create_screen.dart';
import '../features/videos/video_feed_screen.dart';
import '../features/profile/profile_screen.dart';
import '../features/account/account_sessions_screen.dart';
import '../features/account/live_account_screen.dart';
import '../features/discovery/live_video_screen.dart';
import '../features/creators/live_creator_screen.dart';
import '../features/points/live_points_screen.dart';
import 'app_dependencies.dart';
import 'app_session.dart';
import 'screen_route.dart';

class KoloVibeApp extends StatefulWidget {
  const KoloVibeApp({
    super.key,
    this.dependencies = const AppDependencies.unavailable(),
    this.initialScreen = 1,
    this.catalog,
  });
  final AppDependencies dependencies;
  final int initialScreen;
  final DesignCatalog? catalog;
  @override
  State<KoloVibeApp> createState() => _KoloVibeAppState();
}

class _KoloVibeAppState extends State<KoloVibeApp> {
  late final Future<DesignCatalog> catalog;
  final session = AppSession();
  Future<int>? _initialScreenFuture;
  @override
  void initState() {
    super.initState();
    catalog = widget.catalog == null
        ? DesignCatalog.load()
        : Future.value(widget.catalog);
    _initialScreenFuture = _restoreInitialScreen();
  }

  @override
  void dispose() {
    session.dispose();
    super.dispose();
  }

  Future<int>? _restoreInitialScreen() {
    final account = widget.dependencies.liveAccount;
    if (account == null || widget.initialScreen != 1) return null;
    return account.currentAccount().then(
          (user) => user == null ? widget.initialScreen : 17,
        );
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<DesignCatalog>(
        future: catalog,
        builder: (context, design) => FutureBuilder<int>(
          future: _initialScreenFuture,
          builder: (context, startup) => MaterialApp(
            key: ValueKey((
              design.hasData,
              _initialScreenFuture,
              startup.connectionState,
            )),
            title: 'KoloVibe',
            debugShowCheckedModeBanner: false,
            theme: KoloVibeTheme.light(),
            themeMode: ThemeMode.light,
            onGenerateRoute: (settings) {
              final route = settings.arguments is ScreenRoute
                  ? settings.arguments as ScreenRoute
                  : ScreenRoute(startup.data ?? widget.initialScreen);
              if (!route.valid) throw ArgumentError('Unknown mobile screen');
              return MaterialPageRoute<void>(
                settings: RouteSettings(name: route.name, arguments: route),
                builder: (context) => _buildRoute(route, design, startup),
              );
            },
          ),
        ),
      );

  Widget _buildRoute(
    ScreenRoute route,
    AsyncSnapshot<DesignCatalog> design,
    AsyncSnapshot<int> startup,
  ) {
    if (design.hasError) {
      return const Scaffold(
        body: Center(
          child: Text('The interface could not be loaded. Restart KoloVibe.'),
        ),
      );
    }
    if (startup.connectionState == ConnectionState.waiting || !design.hasData) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }
    if (startup.hasError) {
      return Scaffold(
        body: SafeArea(
          child: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text('Your session could not be checked.'),
                FilledButton(
                  onPressed: () {
                    setState(
                        () => _initialScreenFuture = _restoreInitialScreen());
                  },
                  child: const Text('Retry'),
                ),
              ],
            ),
          ),
        ),
      );
    }
    return featureScreen(route, design.data!);
  }

  Widget featureScreen(ScreenRoute route, DesignCatalog catalog) =>
      switch (route.screen) {
        17 ||
        18 ||
        19 ||
        24 when widget.dependencies.liveVideos != null =>
          LiveVideoScreen(
              route: route,
              catalog: catalog,
              repository: widget.dependencies.liveVideos!,
              creators: widget.dependencies.liveCreators,
              account: widget.dependencies.liveAccount),
        25
            when widget.dependencies.liveVideos != null &&
                route.entityId != null =>
          LiveVideoDetailScreen(
              id: route.entityId!, repository: widget.dependencies.liveVideos!),
        38
            when widget.dependencies.liveCreators != null &&
                route.entityId != null =>
          LiveCreatorScreen(
              id: route.entityId!,
              repository: widget.dependencies.liveCreators!,
              account: widget.dependencies.liveAccount),
        >= 61 && <= 69 when widget.dependencies.livePoints != null =>
          LivePointsScreen(
              route: route, repository: widget.dependencies.livePoints!),
        83 when widget.dependencies.liveAccount != null =>
          AccountSessionsScreen(repository: widget.dependencies.liveAccount!),
        79 when widget.dependencies.liveAccount != null => LiveAccountScreen(
            repository: widget.dependencies.liveAccount!, catalog: catalog),
        17 => HomeScreen(
            catalog: catalog,
            dependencies: widget.dependencies,
            session: session),
        19 => ExploreScreen(
            catalog: catalog,
            dependencies: widget.dependencies,
            session: session),
        37 => CreateScreen(
            catalog: catalog,
            dependencies: widget.dependencies,
            session: session),
        24 => VideoFeedScreen(
            catalog: catalog,
            dependencies: widget.dependencies,
            session: session),
        79 => ProfileScreen(
            catalog: catalog,
            dependencies: widget.dependencies,
            session: session),
        _ => MobileScreen(
            route: route,
            catalog: catalog,
            dependencies: widget.dependencies,
            session: session),
      };
}
