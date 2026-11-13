import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/app/screen_route.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/core/presentation/design_node.dart';
import 'package:kolovibe/features/creators/live_become_creator_screen.dart';
import 'package:kolovibe/features/creators/live_creator_studio_screen.dart';
import 'package:kolovibe/features/creators/live_edit_creator_profile_screen.dart';
import 'package:kolovibe/features/creators/live_own_profile_screen.dart';

import 'support/creator_fakes.dart';
import 'support/upload_fakes.dart';

/// Widget tests with scripted (fake) repositories and the real design catalog.
/// No HTTP, platform channels or device APIs are exercised.
void main() {
  late DesignCatalog catalog;
  late ScriptedOnboarding onboarding;
  late ScriptedOwnCreator profiles;
  late List<RouteSettings> pushed;

  setUpAll(() async => catalog = await DesignCatalog.load());
  setUp(() {
    onboarding = ScriptedOnboarding();
    profiles = ScriptedOwnCreator();
    pushed = [];
  });

  Future<void> pump(WidgetTester tester, Widget screen,
      {double textScale = 1}) async {
    await tester.pumpWidget(MaterialApp(
      builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context)
              .copyWith(textScaler: TextScaler.linear(textScale)),
          child: child!),
      home: screen,
      onGenerateRoute: (settings) {
        pushed.add(settings);
        return MaterialPageRoute<void>(
            settings: settings,
            builder: (_) => const Scaffold(body: Text('next screen')));
      },
    ));
    await tester.pumpAndSettle();
  }

  Widget become() =>
      LiveBecomeCreatorScreen(catalog: catalog, onboarding: onboarding);
  Widget studio() => LiveCreatorStudioScreen(
      catalog: catalog, onboarding: onboarding, profiles: profiles);
  Widget profileScreen({int? count}) => LiveOwnProfileScreen(
      catalog: catalog,
      profiles: profiles,
      publicCreators: count == null ? null : CountingPublicCreators(count));
  Widget edit() =>
      LiveEditCreatorProfileScreen(catalog: catalog, profiles: profiles);

  ScreenRoute lastRoute() => pushed.last.arguments as ScreenRoute;

  /// Lists build lazily: scroll the control into view before using it.
  Future<void> reveal(WidgetTester tester, Finder finder) async {
    await tester.scrollUntilVisible(finder, 120,
        scrollable: find.byType(Scrollable).first);
    await tester.pumpAndSettle();
  }

  /// A fresh State for each screen, so every pump starts with a new load.
  Future<void> pumpFresh(WidgetTester tester, Widget screen) async {
    await tester.pumpWidget(const SizedBox());
    await pump(tester, screen);
  }

  group('M-036 Become a creator', () {
    testWidgets('an account without an invitation is told the truth',
        (tester) async {
      await pump(tester, become());
      expect(find.text('From viewer\nto storyteller.'), findsOneWidget);
      expect(find.text('Viewer account'), findsOneWidget);
      expect(
          find.textContaining('none exists for this account'), findsOneWidget);
      expect(find.byType(TextField), findsNothing);
      expect(
          find.widgetWithText(FilledButton, 'Become a creator'), findsNothing);
      // No invented upload path is offered.
      expect(find.text('Open Creator Studio'), findsNothing);
    });

    testWidgets('shows loading first', (tester) async {
      await tester.pumpWidget(MaterialApp(home: become()));
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      await tester.pumpAndSettle();
    });

    testWidgets('offline shows retry, and retry recovers', (tester) async {
      onboarding.failures.add(offline);
      await pump(tester, become());
      expect(find.text('You are offline'), findsOneWidget);
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Viewer account'), findsOneWidget);
    });

    testWidgets('an expired session offers sign-in and returns here',
        (tester) async {
      onboarding.failures.add(expired);
      await pump(tester, become());
      expect(find.text('Session expired'), findsOneWidget);
      await tester.tap(find.text('Sign in'));
      await tester.pumpAndSettle();
      expect(lastRoute().screen, 4);
      expect(lastRoute().returnTo, 36);
    });

    testWidgets(
        'an invited account applies with a valid handle and both statements',
        (tester) async {
      onboarding.status = 'invited';
      await pump(tester, become());
      final apply = find.widgetWithText(FilledButton, 'Become a creator');
      await tester.enterText(find.byType(TextField), 'Ama Kollie');
      await reveal(tester, apply);
      await tester.tap(apply);
      await tester.pumpAndSettle();
      expect(find.textContaining('Use lowercase letters only'), findsOneWidget);
      expect(onboarding.submissions, isEmpty);

      await tester.enterText(find.byType(TextField), 'ama_kollie');
      await tester.tap(apply);
      await tester.pumpAndSettle();
      expect(find.text('Confirm both statements to continue.'), findsOneWidget);
      expect(onboarding.submissions, isEmpty);

      await reveal(tester, find.text('I confirm I am an adult.'));
      await tester.tap(find.text('I confirm I am an adult.'));
      await tester.tap(find.text('I have rights to my original content.'));
      await reveal(tester, apply);
      await tester.tap(apply);
      await tester.pumpAndSettle();
      expect(onboarding.submissions.single,
          {'handle': 'ama_kollie', 'adult': true, 'rights': true});
      expect(find.text('Your creator application is awaiting review.'),
          findsOneWidget);
      expect(find.byType(TextField), findsNothing);
    });

    testWidgets('a conflicting handle is explained on the form',
        (tester) async {
      onboarding
        ..status = 'invited'
        ..submitFailure =
            const ApiFailure(409, 'Application or handle conflict');
      await pump(tester, become());
      await tester.enterText(find.byType(TextField), 'ama_kollie');
      await reveal(tester, find.text('I confirm I am an adult.'));
      await tester.tap(find.text('I confirm I am an adult.'));
      await tester.tap(find.text('I have rights to my original content.'));
      final apply = find.widgetWithText(FilledButton, 'Become a creator');
      await reveal(tester, apply);
      await tester.tap(apply);
      await tester.pumpAndSettle();
      expect(find.textContaining('Choose another handle'), findsOneWidget);
      expect(find.byType(TextField), findsOneWidget);
    });

    testWidgets('rejected, pending and restricted states are distinct',
        (tester) async {
      for (final (status, text) in [
        ('rejected', 'Your creator application was not approved.'),
        ('pending', 'Your creator application is awaiting review.'),
        (
          'approved',
          'Creator upload is currently restricted for this account.'
        ),
      ]) {
        onboarding.status = status;
        await pumpFresh(tester, become());
        expect(find.text(text), findsOneWidget, reason: status);
      }
    });

    testWidgets('an eligible creator is sent to the studio', (tester) async {
      onboarding
        ..eligible = true
        ..status = 'approved';
      await pump(tester, become());
      await tester.tap(find.text('Open Creator Studio'));
      await tester.pumpAndSettle();
      expect(lastRoute().screen, 37);
    });

    testWidgets('the invitation form survives 2.0 text scale', (tester) async {
      onboarding.status = 'invited';
      await pump(tester, become(), textScale: 2);
      await reveal(tester, find.byType(TextField));
      await reveal(
          tester, find.widgetWithText(FilledButton, 'Become a creator'));
      expect(tester.takeException(), isNull);
      expect(find.byType(TextField), findsOneWidget);
    });
  });

  group('M-037 Creator Studio', () {
    testWidgets('an approved creator sees their real name and actions',
        (tester) async {
      onboarding
        ..eligible = true
        ..status = 'approved';
      await pump(tester, studio());
      expect(find.text('Ama Kollie · Creator enabled'), findsOneWidget);
      // No fabricated metrics, Lone Stars or video counts.
      expect(find.textContaining('18.2K'), findsNothing);
      expect(find.textContaining('Lone Stars'), findsNothing);
      for (final (label, screen) in [
        ('Publish an original', 41),
        ('My video library', 40),
        ('Creator profile', 38),
      ]) {
        await tester.tap(find.text(label));
        await tester.pumpAndSettle();
        expect(lastRoute().screen, screen, reason: label);
        Navigator.of(tester.element(find.text('next screen'))).pop();
        await tester.pumpAndSettle();
      }
    });

    testWidgets('a viewer sees onboarding instead of the studio',
        (tester) async {
      await pump(tester, studio());
      expect(find.text('Viewer account'), findsOneWidget);
      expect(find.text('Publish an original'), findsNothing);
      expect(profiles.reads, 0);
    });

    testWidgets('a restricted creator profile is shown as not available',
        (tester) async {
      onboarding
        ..eligible = true
        ..status = 'approved';
      profiles.profileFailure =
          const ApiFailure(403, 'Creator profile restricted or suspended');
      await pump(tester, studio());
      expect(find.text('Not available'), findsOneWidget);
      expect(find.text('Publish an original'), findsNothing);
    });

    testWidgets('profile outage offers retry', (tester) async {
      onboarding
        ..eligible = true
        ..status = 'approved';
      profiles.profileFailure = offline;
      await pump(tester, studio());
      expect(find.text('You are offline'), findsOneWidget);
      profiles.profileFailure = null;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Ama Kollie · Creator enabled'), findsOneWidget);
    });
  });

  group('M-038 Creator profile', () {
    testWidgets('shows the real public fields and routes to the right places',
        (tester) async {
      await pump(tester, profileScreen(count: 12));
      expect(find.text('Ama Kollie'), findsOneWidget);
      expect(find.text('@amakollie · Monrovia'), findsOneWidget);
      expect(find.text('Finding the cinema in the everyday.'), findsOneWidget);
      expect(find.text('12 videos'), findsOneWidget);

      await tester.tap(find.text('Public profile preview'));
      await tester.pumpAndSettle();
      expect(lastRoute().screen, 26);
      expect(lastRoute().entityId, creatorId);
      Navigator.of(tester.element(find.text('next screen'))).pop();
      await tester.pumpAndSettle();

      await tester.tap(find.text('Published originals'));
      await tester.pumpAndSettle();
      expect(lastRoute().screen, 27);
      expect(lastRoute().entityId, creatorId);
    });

    testWidgets('an unavailable public count is omitted, not invented',
        (tester) async {
      await pump(tester, profileScreen());
      expect(find.text('Published originals'), findsOneWidget);
      expect(find.textContaining('videos'), findsNothing);
    });

    testWidgets('an empty bio is stated plainly', (tester) async {
      profiles.current = ownCreator(bio: '', name: '', location: '');
      await pump(tester, profileScreen());
      expect(find.text('You haven’t written a bio yet.'), findsOneWidget);
      expect(find.text('@amakollie'), findsNWidgets(2)); // title and facts
    });

    testWidgets('editing reloads the profile after a saved change',
        (tester) async {
      await pump(tester, profileScreen());
      expect(profiles.reads, 1);
      await reveal(tester, find.text('Edit creator profile'));
      await tester.tap(find.text('Edit creator profile'));
      await tester.pumpAndSettle();
      expect(lastRoute().screen, 39);
      Navigator.of(tester.element(find.text('next screen'))).pop(true);
      await tester.pumpAndSettle();
      expect(profiles.reads, 2);
    });

    testWidgets('offline and expired states', (tester) async {
      profiles.profileFailure = offline;
      await pump(tester, profileScreen());
      expect(find.text('You are offline'), findsOneWidget);
      profiles.profileFailure = expired;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Sign in'));
      await tester.pumpAndSettle();
      expect(lastRoute().screen, 4);
      expect(lastRoute().returnTo, 38);
    });

    testWidgets('a missing profile is not found', (tester) async {
      profiles.profileFailure = const ApiFailure(404, 'Own profile not found');
      await pump(tester, profileScreen());
      expect(find.text('Not found'), findsOneWidget);
    });
  });

  group('M-039 Edit creator profile', () {
    Finder field(String label) => find.widgetWithText(TextField, label);

    testWidgets('starts filled, unchanged and not savable; offers no photo',
        (tester) async {
      await pump(tester, edit());
      expect(find.text('Ama Kollie'), findsOneWidget);
      expect(find.text('amakollie'), findsOneWidget);
      expect(find.text('Change profile photo'), findsNothing);
      final save = tester.widget<FilledButton>(
          find.widgetWithText(FilledButton, 'Save profile'));
      expect(save.onPressed, isNull);
    });

    testWidgets('saves only after a change and returns true', (tester) async {
      bool? result;
      await tester.pumpWidget(MaterialApp(
          home: Builder(
              builder: (context) => Scaffold(
                  body: TextButton(
                      onPressed: () async => result =
                          await Navigator.of(context).push<bool>(
                              MaterialPageRoute(builder: (_) => edit())),
                      child: const Text('open'))))));
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();
      await tester.enterText(field('Display name'), '  Ama K.  ');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Save profile'));
      await tester.pumpAndSettle();
      expect(profiles.updates.single['display_name'], '  Ama K.  ');
      expect(profiles.current.displayName, 'Ama K.');
      expect(result, isTrue);
    });

    testWidgets('a handle with a space is explained and never sent',
        (tester) async {
      await pump(tester, edit());
      await tester.enterText(field('Creator handle'), 'ama kollie');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Save profile'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Spaces aren’t allowed'), findsOneWidget);
      expect(profiles.updates, isEmpty);
    });

    testWidgets('a taken handle keeps the form and the typed values',
        (tester) async {
      profiles.updateFailure =
          const ApiFailure(409, 'unavailable', code: 'handle_taken');
      await pump(tester, edit());
      await tester.enterText(field('Creator handle'), 'taken_one');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Save profile'));
      await tester.pumpAndSettle();
      expect(find.text('That handle is already taken. Choose another.'),
          findsOneWidget);
      expect(find.text('taken_one'), findsOneWidget);
    });

    testWidgets('offline keeps the changes and says so', (tester) async {
      profiles.updateFailure = offline;
      await pump(tester, edit());
      await tester.enterText(field('Location'), 'Paynesville');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Save profile'));
      await tester.pumpAndSettle();
      expect(find.textContaining('You are offline'), findsOneWidget);
      expect(find.text('Paynesville'), findsOneWidget);
      // A later reload does not overwrite what the user typed.
      expect(profiles.reads, 1);
    });

    testWidgets('an expired session offers sign-in without losing the form',
        (tester) async {
      profiles.updateFailure = expired;
      await pump(tester, edit());
      await tester.enterText(field('Bio'), 'A new bio');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Save profile'));
      await tester.pumpAndSettle();
      expect(find.text('Sign in again'), findsOneWidget);
      expect(find.text('A new bio'), findsOneWidget);
    });

    testWidgets('a restricted creator sees the reason', (tester) async {
      profiles.profileFailure =
          const ApiFailure(403, 'Creator profile restricted or suspended');
      await pump(tester, edit());
      expect(find.text('Not available'), findsOneWidget);
      expect(find.widgetWithText(FilledButton, 'Save profile'), findsNothing);
    });

    testWidgets('the form survives 2.0 text scale', (tester) async {
      await pump(tester, edit(), textScale: 2);
      await reveal(tester, find.widgetWithText(TextField, 'Creator handle'));
      await reveal(tester, find.widgetWithText(FilledButton, 'Save profile'));
      expect(tester.takeException(), isNull);
      expect(find.widgetWithText(TextField, 'Creator handle'), findsOneWidget);
    });
  });
}
