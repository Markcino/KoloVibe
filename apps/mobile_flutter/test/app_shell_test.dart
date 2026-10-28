import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kolovibe/app/kolovibe_app.dart';

void main() {
  testWidgets('KoloVibe has five primary destinations', (tester) async {
    await tester.pumpWidget(const KoloVibeApp());

    expect(find.byType(NavigationBar), findsOneWidget);
    expect(find.byType(NavigationDestination), findsNWidgets(5));
    expect(find.text('Home'), findsOneWidget);
    expect(find.text('Explore'), findsOneWidget);
    expect(find.text('Create'), findsOneWidget);
    expect(find.text('Videos'), findsOneWidget);
    expect(find.text('Profile'), findsOneWidget);
  });

  testWidgets('Video destination is a separate full-screen experience', (tester) async {
    await tester.pumpWidget(const KoloVibeApp());
    await tester.tap(find.byIcon(Icons.smart_display_outlined).first);
    await tester.pumpAndSettle();

    expect(find.text('For You'), findsOneWidget);
    expect(find.text('Following'), findsOneWidget);
    expect(find.text('Original video lives here.'), findsOneWidget);
  });
}
