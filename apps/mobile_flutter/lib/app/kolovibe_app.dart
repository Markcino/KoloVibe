import 'package:flutter/material.dart';
import '../core/theme/kolovibe_theme.dart';
import '../features/shell/main_shell.dart';

class KoloVibeApp extends StatelessWidget {
  const KoloVibeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'KoloVibe',
      debugShowCheckedModeBanner: false,
      theme: KoloVibeTheme.light(),
      darkTheme: KoloVibeTheme.dark(),
      themeMode: ThemeMode.system,
      home: const MainShell(),
    );
  }
}
