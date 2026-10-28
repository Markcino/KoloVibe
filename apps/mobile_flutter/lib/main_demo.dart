import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'app/app_dependencies.dart';
import 'app/kolovibe_app.dart';
import 'demo/demo_repository.dart';

void main() {
  if (kReleaseMode) {
    throw UnsupportedError('The demo entry point cannot run in release mode.');
  }
  runApp(
    KoloVibeApp(
      dependencies: AppDependencies.preview(DemoRepository().services),
    ),
  );
}
