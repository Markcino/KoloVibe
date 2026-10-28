import 'package:flutter/material.dart';

abstract final class KoloVibeColors {
  static const navy = Color(0xFF102A56);
  static const deepNavy = Color(0xFF001539);
  static const red = Color(0xFFE02736);
  static const gold = Color(0xFFF9BD22);
  static const lavender = Color(0xFFF0F3FF);
  static const softBlue = Color(0xFFE7EEFF);
  static const ink = Color(0xFF283140);
  static const muted = Color(0xFF697184);
  static const green = Color(0xFF16875D);
}

abstract final class KoloVibeTheme {
  static ThemeData light() => _build(Brightness.light);
  static ThemeData dark() => _build(Brightness.dark);

  static ThemeData _build(Brightness brightness) {
    final dark = brightness == Brightness.dark;
    final scheme = ColorScheme.fromSeed(
      seedColor: KoloVibeColors.navy,
      brightness: brightness,
      primary: dark ? const Color(0xFFB4CBFF) : KoloVibeColors.navy,
      secondary: KoloVibeColors.red,
      surface: dark ? const Color(0xFF0D1C34) : Colors.white,
    );
    final base = ThemeData(useMaterial3: true, colorScheme: scheme);
    return base.copyWith(
      scaffoldBackgroundColor: dark ? const Color(0xFF08182B) : KoloVibeColors.lavender,
      textTheme: base.textTheme.copyWith(
        headlineLarge: base.textTheme.headlineLarge?.copyWith(fontWeight: FontWeight.w800, letterSpacing: -0.8),
        headlineMedium: base.textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800, letterSpacing: -0.5),
        titleLarge: base.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surface,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide.none),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      ),
      cardTheme: CardThemeData(
        color: scheme.surface,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: scheme.surface,
        indicatorColor: dark ? KoloVibeColors.navy : KoloVibeColors.softBlue,
        height: 76,
      ),
    );
  }
}
