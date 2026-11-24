import 'package:flutter/material.dart';

import '../../app/screen_route.dart';
import '../../core/presentation/design_node.dart';
import '../../shared/widgets/kolo_components.dart';
import 'business_page.dart';

/// Shown only for a Business screen number that has no screen yet. It contains no data and no action.
class BusinessPendingScreen extends StatelessWidget {
  const BusinessPendingScreen(
      {super.key,
      required this.route,
      required this.catalog,
      this.available = true});
  final ScreenRoute route;
  final DesignCatalog catalog;
  final bool available;

  @override
  Widget build(BuildContext context) => BusinessPage(
        screen: route.screen,
        catalog: catalog,
        title: 'Businesses',
        child: KoloNote(
          title: available ? 'Not available yet' : 'Businesses are unavailable',
          message: available
              ? 'This part of Businesses is not available in this version.'
              : 'KoloVibe cannot reach its service right now. Try again later.',
        ),
      );
}
