import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/app/kolovibe_app.dart';
import 'package:kolovibe/core/presentation/design_node.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late DesignCatalog catalog;
  setUpAll(() async => catalog = await DesignCatalog.load());
  testWidgets('Unauthenticated account access cannot create a session',
      (tester) async {
    await tester.pumpWidget(KoloVibeApp(catalog: catalog, initialScreen: 17));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 450));
    expect(find.text('This service is not connected yet.'), findsOneWidget);
  });
  testWidgets('Sign in fails closed without a connected identity service',
      (tester) async {
    await tester.pumpWidget(KoloVibeApp(catalog: catalog, initialScreen: 4));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 450));
    expect(find.text('Good morning, Ama ☀'), findsNothing);
  });
}
