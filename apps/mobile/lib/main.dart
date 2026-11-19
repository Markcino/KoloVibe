import 'package:flutter/material.dart';
import 'app/kolovibe_app.dart';
import 'app/app_dependencies.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  const gateway = String.fromEnvironment('KOLOVIBE_API_URL');
  runApp(KoloVibeApp(
      dependencies: gateway.isEmpty
          ? const AppDependencies.unavailable()
          : AppDependencies.live(gateway)));
}
