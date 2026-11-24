import 'package:flutter/material.dart';

import '../../shared/widgets/kolo_components.dart';
import 'business_page.dart';
import 'business_screens.dart';

/// Shown when the service says the person no longer has a business: it was closed, their access was removed, or they
/// left. Nothing from the business is shown, and no action on it is offered.
class AccessRemovedBody extends StatelessWidget {
  const AccessRemovedBody({super.key});

  @override
  Widget build(BuildContext context) => Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: KoloStatePanel(
            icon: Icons.lock_outline,
            label: 'Access removed',
            headline: 'You no longer have access to this business.',
            message:
                'The business may have removed you from its team, or it may be closed. Ask the owner if you think this is a mistake.',
            actions: [
              FilledButton(
                key: const ValueKey('access-removed-choose'),
                onPressed: () =>
                    openBusiness(context, BusinessScreens.switcher),
                child: const Text('Choose another business'),
              ),
              OutlinedButton(
                onPressed: () =>
                    openBusiness(context, BusinessScreens.myBusinesses),
                child: const Text('My businesses'),
              ),
            ],
          ),
        ),
      );
}
