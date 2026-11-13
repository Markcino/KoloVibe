// Widget tests use fake repositories and an in-memory picked file: no HTTP,
// storage, platform picker or device APIs are exercised.
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';
import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/features/content/live_create_original_screen.dart';
import 'package:kolovibe/features/content/live_upload_controller.dart';
import 'support/upload_fakes.dart';

void main() {
  late FakeContent content;
  late FakeOnboarding onboarding;
  late List<String> routes;
  late Completer<void> pollGate;

  Future<void> open(WidgetTester tester,
      {double textScale = 1, XFile? Function()? picker}) async {
    routes = [];
    pollGate = Completer<void>();
    final controller = LiveUploadController(content, onboarding,
        delay: (_) => pollGate.future);
    await tester.pumpWidget(MaterialApp(
      builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context)
              .copyWith(textScaler: TextScaler.linear(textScale)),
          child: child!),
      onGenerateRoute: (settings) {
        routes.add(settings.name!);
        return MaterialPageRoute<void>(
            settings: settings,
            builder: (_) => Scaffold(body: Text('route ${settings.name}')));
      },
      home: LiveCreateOriginalScreen(
        content: content,
        onboarding: onboarding,
        controller: controller,
        pickVideo: () async => (picker ?? mp4)(),
      ),
    ));
    await tester.pump();
  }

  Future<void> choose(WidgetTester tester) async {
    await tester.tap(find.text('Select a video'));
    await tester.pump();
    await tester.pump();
  }

  /// The screen is a lazy ListView: scroll until the target is built.
  Future<void> show(WidgetTester tester, Finder target,
      {bool settle = false}) async {
    if (target.evaluate().isEmpty) {
      await tester.scrollUntilVisible(target, 200,
          scrollable: find.byType(Scrollable).first);
    }
    await tester.ensureVisible(target);
    // Text entry starts a caret-reveal scroll; wait for it on form fields only
    // (indeterminate progress bars never settle).
    settle ? await tester.pumpAndSettle() : await tester.pump();
  }

  Future<void> fill(WidgetTester tester) async {
    final title = find.widgetWithText(TextField, 'Title · Required');
    await show(tester, title);
    await tester.enterText(title, 'Walls that speak');
    final description = find.widgetWithText(TextField, 'Description');
    await show(tester, description, settle: true);
    await tester.enterText(description, 'A story');
    final dropdown = find.byType(DropdownButtonFormField<String>);
    await show(tester, dropdown, settle: true);
    await tester.tap(dropdown);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Culture').last);
    await tester.pumpAndSettle();
    final tags = find.widgetWithText(TextField, 'Hashtags · Optional');
    await show(tester, tags, settle: true);
    await tester.enterText(tags, '#Monrovia art');
  }

  Future<void> submit(WidgetTester tester) async {
    final button = find.text('Create and upload');
    await show(tester, button, settle: true);
    await tester.tap(button);
    await tester.pump();
    await tester.pump();
  }

  setUp(() {
    content = FakeContent();
    onboarding = FakeOnboarding();
  });

  group('access states', () {
    testWidgets('shows a checking state, then the M-041 entry', (tester) async {
      await open(tester);
      expect(find.text('Choose your video'), findsOneWidget);
      expect(find.text('Select a video'), findsOneWidget);
      expect(find.textContaining('own or have permission'), findsOneWidget);
    });

    testWidgets('an ineligible account sees no upload form', (tester) async {
      onboarding.eligible = false;
      await open(tester);
      expect(find.text('Creator upload is not available for this account.'),
          findsOneWidget);
      expect(find.text('Select a video'), findsNothing);
      onboarding.eligible = true;
      await tester.tap(find.text('Check again'));
      await tester.pump();
      expect(find.text('Select a video'), findsOneWidget);
    });

    testWidgets('an outage offers a retry', (tester) async {
      onboarding.error = const ApiFailure(503, 'Service unavailable');
      await open(tester);
      expect(find.text('Service unavailable'), findsOneWidget);
      await tester.tap(find.text('Retry creator access'));
      await tester.pump();
      expect(find.text('Select a video'), findsOneWidget);
    });

    testWidgets('an expired session routes to sign in', (tester) async {
      onboarding.error = const ApiFailure(401, 'expired');
      await open(tester);
      expect(find.text('Session expired'), findsOneWidget);
      await tester.tap(find.text('Sign in'));
      await tester.pumpAndSettle();
      expect(routes, contains('/mobile/M-004'));
    });

    testWidgets('a restricted creator is told nothing was published',
        (tester) async {
      onboarding.error = const ApiFailure(403, 'forbidden');
      await open(tester);
      expect(
          find.textContaining('not available for this account'), findsWidgets);
      expect(find.textContaining('Nothing was published'), findsOneWidget);
      expect(find.text('Select a video'), findsNothing);
    });
  });

  group('file and story steps', () {
    testWidgets('a rejected file shows the check failure and no form',
        (tester) async {
      await open(tester, picker: () => mp4(name: 'story.mov'));
      await choose(tester);
      expect(find.text('Select an MP4 video under 50 MB.'), findsOneWidget);
      expect(find.text('Title · Required'), findsNothing);
    });

    testWidgets('a cancelled picker changes nothing', (tester) async {
      await open(tester, picker: () => null);
      await choose(tester);
      expect(find.text('Title · Required'), findsNothing);
    });

    testWidgets('required details are enforced before any request',
        (tester) async {
      await open(tester);
      await choose(tester);
      expect(find.text('File checked · Ready for details'), findsOneWidget);
      await submit(tester);
      expect(find.text('Enter a title.'), findsOneWidget);
      expect(find.text('Select a category to continue.'), findsOneWidget);
      expect(content.events, isEmpty);
    });
  });

  group('transfer states', () {
    testWidgets('shows real progress while uploading (M-046)', (tester) async {
      content.transferGate = Completer<void>();
      await open(tester);
      await choose(tester);
      await fill(tester);
      await submit(tester);
      expect(find.text('Uploading your original'), findsOneWidget);
      expect(find.text('50%'), findsOneWidget);
      final bar = tester.widget<LinearProgressIndicator>(
          find.byType(LinearProgressIndicator));
      expect(bar.value, 0.5);
      expect(find.textContaining('Keep KoloVibe open'), findsOneWidget);
      content.transferGate!.complete();
      await tester.pump();
      await tester.pump();
      expect(find.text('Preparing your video'), findsOneWidget);
    });

    testWidgets('an interruption keeps the draft and retries (M-047)',
        (tester) async {
      content.transferError = const ApiFailure(503, 'cut', offline: true);
      await open(tester);
      await choose(tester);
      await fill(tester);
      await submit(tester);
      expect(find.text('Upload interrupted'), findsOneWidget);
      expect(find.textContaining('offline'), findsOneWidget);
      expect(find.textContaining('has not been published'), findsOneWidget);
      await tester.tap(find.text('Check connection and retry'));
      await tester.pump();
      await tester.pump();
      expect(find.text('Preparing your video'), findsOneWidget);
      expect(content.events.where((e) => e == 'draft'), hasLength(1));
      expect(content.uploadKeys.toSet(), hasLength(1));
    });

    testWidgets('a confirmed failure explains the reason and retries (M-048)',
        (tester) async {
      content.completion =
          FakeContent.status('failed', reason: 'upload_missing');
      await open(tester);
      await choose(tester);
      await fill(tester);
      await submit(tester);
      expect(find.text('Upload failed'), findsOneWidget);
      expect(find.textContaining('did not confirm receipt'), findsOneWidget);
      content.completion = FakeContent.status('processing');
      await tester.tap(find.text('Retry upload'));
      await tester.pump();
      await tester.pump();
      expect(find.text('Preparing your video'), findsOneWidget);
      expect(content.uploadKeys.toSet(), hasLength(2));
    });

    testWidgets('invalid media asks for a different video, not a retry',
        (tester) async {
      content.completion =
          FakeContent.status('failed', reason: 'invalid_media');
      await open(tester);
      await choose(tester);
      await fill(tester);
      await submit(tester);
      expect(find.textContaining("couldn't validate"), findsOneWidget);
      expect(find.text('Retry upload'), findsNothing);
      expect(find.text('Select a different video'), findsOneWidget);
    });
  });

  group('preparation and outcomes', () {
    testWidgets('preparing offers the library and never claims publication',
        (tester) async {
      await open(tester);
      await choose(tester);
      await fill(tester);
      await submit(tester);
      expect(find.text('Upload received'), findsOneWidget);
      expect(find.textContaining('not public yet'), findsOneWidget);
      expect(find.textContaining('Video status: published'), findsNothing);
      await show(tester, find.text('Return to my library'));
      await tester.tap(find.text('Return to my library'));
      await tester.pumpAndSettle();
      expect(routes, contains('/mobile/M-040'));
    });

    testWidgets('a transient preparation failure offers a retry',
        (tester) async {
      content.completion =
          FakeContent.status('processing', reason: 'processing_unavailable');
      await open(tester);
      await choose(tester);
      await fill(tester);
      await submit(tester);
      expect(find.textContaining('temporarily unavailable'), findsOneWidget);
      content.completion = FakeContent.status('review');
      await tester.tap(find.text('Retry preparation'));
      await tester.pump();
      await tester.pump();
      expect(find.text('Video status: review'), findsOneWidget);
    });

    testWidgets('review is reported as not public; no decision is invented',
        (tester) async {
      content.completion = FakeContent.status('review');
      await open(tester);
      await choose(tester);
      await fill(tester);
      await submit(tester);
      expect(find.textContaining('waiting for review'), findsOneWidget);
      expect(find.textContaining('approved'), findsNothing);
    });

    testWidgets('automatic status checks stop and offer a manual check',
        (tester) async {
      final controller = LiveUploadController(content, onboarding,
          delay: (_) async {}, maxPolls: 2);
      routes = [];
      await tester.pumpWidget(MaterialApp(
        home: LiveCreateOriginalScreen(
          content: content,
          onboarding: onboarding,
          controller: controller,
          pickVideo: () async => mp4(),
        ),
      ));
      await tester.pump();
      await choose(tester);
      await fill(tester);
      await submit(tester);
      await tester.pump();
      expect(find.textContaining('stopped checking'), findsOneWidget);
      content.statusQueue.add(FakeContent.status('published'));
      await show(tester, find.text('Check again'));
      await tester.tap(find.text('Check again'));
      await tester.pump();
      await tester.pump();
      expect(find.text('Video status: published'), findsOneWidget);
    });
  });

  group('accessibility', () {
    for (final scale in [1.0, 2.0]) {
      testWidgets('form and failure states lay out at text scale $scale',
          (tester) async {
        content.completion =
            FakeContent.status('failed', reason: 'upload_missing');
        await open(tester, textScale: scale);
        await choose(tester);
        await fill(tester);
        await submit(tester);
        expect(find.text('Upload failed'), findsOneWidget);
        expect(tester.takeException(), isNull);
        final semantics = tester.getSemantics(find.text('Upload failed'));
        expect(semantics.label, 'Upload failed');
      });
    }

    testWidgets('progress is exposed to assistive technology', (tester) async {
      final handle = tester.ensureSemantics();
      content.transferGate = Completer<void>();
      await open(tester);
      await choose(tester);
      await fill(tester);
      await submit(tester);
      expect(find.bySemanticsLabel('Upload progress'), findsOneWidget);
      content.transferGate!.complete();
      await tester.pump();
      handle.dispose();
    });
  });
}
