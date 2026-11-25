import 'package:flutter/material.dart';

import '../core/presentation/design_node.dart';
import '../core/theme/kolovibe_theme.dart';
import '../features/shell/mobile_screen.dart';
import '../features/home/home_screen.dart';
import '../features/explore/explore_screen.dart';
import '../features/create/create_screen.dart';
import '../features/videos/video_feed_screen.dart';
import '../features/profile/profile_screen.dart';
import '../features/system/compatibility.dart';
import '../features/system/system_ui.dart';
import '../features/legal/legal_screens.dart';
import '../features/legal/live_legal_repository.dart';
import 'app_dependencies.dart';
import 'app_session.dart';
import 'screen_route.dart';
import 'routes/account_routes.dart';
import 'routes/business_routes.dart';
import 'routes/creator_routes.dart';
import 'routes/discovery_routes.dart';
import 'routes/route_context.dart';
import 'routes/settings_routes.dart';
import 'routes/trust_routes.dart';

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
  Future<CompatibilityPolicy>? _compatibility;
  bool _updateDismissed = false;
  LegalGateController? _legal;
  @override
  void initState() {
    super.initState();
    catalog = widget.catalog == null
        ? DesignCatalog.load()
        : Future.value(widget.catalog);
    _initialScreenFuture = _restoreInitialScreen();
    if (widget.initialScreen == 1 && widget.dependencies.api != null) {
      _compatibility = CompatibilityRepository(
        widget.dependencies.api!,
        widget.dependencies.device,
      ).check();
    }
  }

  @override
  void dispose() {
    session.dispose();
    super.dispose();
  }

  Future<int>? _restoreInitialScreen() {
    final account = widget.dependencies.liveAccount;
    if (account == null || widget.initialScreen != 1) return null;
    return account.restoreSession().then(
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
            builder: (context, child) => FutureBuilder<CompatibilityPolicy>(
              future: _compatibility,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Scaffold(body: SafeArea(child: SystemLoading()));
                }
                final policy =
                    snapshot.data ?? const CompatibilityPolicy.unknown();
                if (policy.required) {
                  return CompatibilityScreen(
                    policy: policy,
                    device: widget.dependencies.device,
                    onRetry: () => setState(() {
                      _compatibility = CompatibilityRepository(
                              widget.dependencies.api!,
                              widget.dependencies.device)
                          .check();
                    }),
                  );
                }
                if (policy.available && !_updateDismissed) {
                  return Column(
                    children: [
                      OptionalUpdateNotice(
                        policy: policy,
                        device: widget.dependencies.device,
                        onDismiss: () =>
                            setState(() => _updateDismissed = true),
                      ),
                      Expanded(child: child!),
                    ],
                  );
                }
                return child!;
              },
            ),
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
      return const Scaffold(body: SafeArea(child: SystemLoading()));
    }
    if (startup.hasError) {
      return Scaffold(
        body: SafeArea(
          child: SystemFailureView(
            error: startup.error!,
            onSignIn: () => setState(() {
              _initialScreenFuture = Future.value(4);
            }),
            onRetry: () => setState(() {
              _initialScreenFuture = _restoreInitialScreen();
            }),
          ),
        ),
      );
    }
    final screen = featureScreen(route, design.data!);
    final account = widget.dependencies.liveAccount;
    final accountId = account?.signedInAccountId;
    if (account == null ||
        accountId == null ||
        LegalAcceptanceGate.exemptScreens.contains(route.screen)) {
      return screen;
    }
    _legal ??= LegalGateController(LiveLegalRepository(account));
    return Builder(
      builder: (context) => LegalAcceptanceGate(
        controller: _legal!,
        accountId: accountId,
        onSignOut: () async {
          await account.signOut();
          if (!context.mounted) return;
          const target = ScreenRoute(2);
          Navigator.of(context).pushNamedAndRemoveUntil(target.name, (_) => false, arguments: target);
        },
        onPrivacy: () {
          const target = ScreenRoute(84);
          Navigator.of(context).pushNamed(target.name, arguments: target);
        },
        child: screen,
      ),
    );
  }

  static const List<DomainRouteBuilder> domainRoutes = [
    accountRoute,
    discoveryRoute,
    creatorRoute,
    trustRoute,
    settingsRoute,
    businessRoute,
  ];

  Widget featureScreen(ScreenRoute route, DesignCatalog catalog) {
    final context = RouteContext(
      route: route,
      catalog: catalog,
      dependencies: widget.dependencies,
      session: session,
    );
    for (final build in domainRoutes) {
      final screen = build(context);
      if (screen != null) return screen;
    }
    return switch (route.screen) {
      17 => HomeScreen(
          catalog: catalog,
          dependencies: widget.dependencies,
          session: session,
        ),
      19 => ExploreScreen(
          catalog: catalog,
          dependencies: widget.dependencies,
          session: session,
        ),
      37 => CreateScreen(
          catalog: catalog,
          dependencies: widget.dependencies,
          session: session,
        ),
      24 => VideoFeedScreen(
          catalog: catalog,
          dependencies: widget.dependencies,
          session: session,
        ),
      79 => ProfileScreen(
          catalog: catalog,
          dependencies: widget.dependencies,
          session: session,
        ),
      _ => MobileScreen(
          route: route,
          catalog: catalog,
          dependencies: widget.dependencies,
          session: session,
        ),
    };
  }
}
