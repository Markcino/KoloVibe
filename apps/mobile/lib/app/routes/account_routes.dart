import 'package:flutter/widgets.dart';

import 'route_context.dart';
import '../../features/account/live_account_flow.dart';
import '../../features/settings/live_information_screen.dart';

/// Welcome, sign-up, sign-in, verification, and recovery (M-001–M-016).
Widget? accountRoute(RouteContext context) {
  final account = context.dependencies.liveAccount;
  if (account == null) return null;
  final id = context.route.screen;
  if (id <= 16 && accountFormScreens.contains(id)) {
    return LiveAccountFlowScreen(
      screen: id,
      account: account,
      catalog: context.catalog,
    );
  }
  if (id == 14) {
    return LiveInformationScreen(
      screen: id,
      catalog: context.catalog,
      account: account,
      device: context.dependencies.device,
    );
  }
  return null;
}
