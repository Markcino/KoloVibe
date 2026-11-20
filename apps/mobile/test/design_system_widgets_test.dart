import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/core/theme/kolovibe_theme.dart';
import 'package:kolovibe/shared/widgets/kolo_components.dart';
import 'support/audit_harness.dart';

/// Contract tests for the shared design components and theme tokens that the
/// restyled screens depend on.
void main() {
  setUpAll(loadBrandFonts);

  Widget host(Widget child, {ThemeData? theme}) => MaterialApp(
      theme: theme ?? KoloVibeTheme.light(), home: Scaffold(body: child));

  group('theme tokens', () {
    test('buttons, inputs and app bar use the approved styling', () {
      final theme = KoloVibeTheme.light();
      final filled = theme.filledButtonTheme.style!;
      expect(filled.backgroundColor!.resolve({}), KoloVibeColors.red);
      expect(filled.minimumSize!.resolve({})!.height, 50);
      expect(theme.outlinedButtonTheme.style!.backgroundColor!.resolve({}),
          KoloVibeColors.softBlue);
      expect(theme.scaffoldBackgroundColor, KoloVibeColors.lavender);
      expect(theme.appBarTheme.scrolledUnderElevation, 0);
      expect(theme.appBarTheme.titleTextStyle!.fontFamily, 'PlusJakartaSans');
      expect(theme.textTheme.bodyMedium!.fontFamily, 'Inter');
      final border =
          theme.inputDecorationTheme.enabledBorder! as OutlineInputBorder;
      expect(border.borderSide.color, KoloVibeColors.line);
    });

    test('the dark surface is the deep navy used by Creator Studio', () {
      expect(KoloVibeTheme.dark().scaffoldBackgroundColor,
          KoloVibeColors.deepNavy);
    });
  });

  group('KoloTextField', () {
    testWidgets('puts the label above the box and toggles a secret',
        (tester) async {
      final controller = TextEditingController(text: 'hunter22');
      await tester.pumpWidget(host(KoloTextField(
          label: 'Password', controller: controller, secret: true)));
      expect(find.text('Password'), findsOneWidget);
      expect(
          tester.widget<TextField>(find.byType(TextField)).obscureText, isTrue);
      expect(tester.getTopLeft(find.text('Password')).dy,
          lessThan(tester.getTopLeft(find.byType(TextField)).dy));
      await tester.tap(find.byTooltip('Show'));
      await tester.pump();
      expect(tester.widget<TextField>(find.byType(TextField)).obscureText,
          isFalse);
    });

    testWidgets('read-only fields cannot be edited', (tester) async {
      await tester.pumpWidget(host(KoloTextField(
          label: 'Account email',
          controller: TextEditingController(text: 'a@b.test'),
          readOnly: true)));
      expect(tester.widget<TextField>(find.byType(TextField)).readOnly, isTrue);
    });
  });

  group('tap targets', () {
    testWidgets('list rows, chips and pills are at least 44 pt',
        (tester) async {
      await tester.pumpWidget(host(Column(children: [
        KoloListRow(title: 'Privacy policy', onTap: () {}),
        Row(children: [
          KoloChip(label: 'Hipco', onTap: () {}),
          KoloPillButton(label: 'Follow', onPressed: () {}),
        ]),
      ])));
      for (final finder in [
        find.widgetWithText(InkWell, 'Privacy policy'),
        find.widgetWithText(InkWell, 'Hipco'),
        find.widgetWithText(InkWell, 'Follow'),
      ]) {
        expect(tester.getSize(finder).height, greaterThanOrEqualTo(44));
      }
    });

    testWidgets('actions are announced as buttons', (tester) async {
      final handle = tester.ensureSemantics();
      await tester
          .pumpWidget(host(KoloPillButton(label: 'Follow', onPressed: () {})));
      final data = tester.getSemantics(find.text('Follow')).getSemanticsData();
      expect(data.label, 'Follow');
      expect(data.flagsCollection.isButton, isTrue);
      handle.dispose();
    });
  });

  group('state and statistic panels', () {
    testWidgets('KoloStatePanel shows medallion, headline and actions',
        (tester) async {
      var retried = false;
      await tester.pumpWidget(host(KoloStatePanel(
          icon: Icons.cloud_off_outlined,
          label: 'Service unavailable',
          headline: 'The stage is quiet for a moment.',
          message: 'Try again later.',
          actions: [
            FilledButton(
                onPressed: () => retried = true, child: const Text('Try again'))
          ])));
      expect(find.text('The stage is quiet for a moment.'), findsOneWidget);
      await tester.tap(find.text('Try again'));
      expect(retried, isTrue);
    });

    testWidgets('KoloHeroStat renders dark and light variants', (tester) async {
      await tester.pumpWidget(host(const Column(children: [
        KoloHeroStat(dark: true, value: '1,240', caption: 'Confirmed'),
        KoloHeroStat(value: '40 withheld', caption: 'Excluded'),
      ])));
      final dark = tester.widget<Text>(find.text('1,240'));
      final light = tester.widget<Text>(find.text('40 withheld'));
      expect(dark.style!.color, KoloVibeColors.gold);
      expect(light.style!.color, KoloVibeColors.navy);
    });

    testWidgets('long text at 3x does not overflow the shared widgets',
        (tester) async {
      useViewport(tester, AuditViewport.small, textScale: 3);
      await tester.pumpWidget(host(SingleChildScrollView(
          child: Column(children: [
        const KoloWordmark(),
        KoloSearchBar(hint: 'Search videos, creators…', onTap: () {}),
        const KoloNote(
            title: 'A long informational title that wraps',
            message: 'Explanatory text that is also fairly long and wraps.'),
        KoloSectionHeading(
            title: 'Creators to know', actionLabel: 'See all', onAction: () {}),
        const KoloAvatar(name: 'Esi Kollie'),
      ]))));
      expect(tester.takeException(), isNull);
    });
  });
}
