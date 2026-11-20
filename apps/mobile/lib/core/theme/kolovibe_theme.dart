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

  /// Hairline border for fields, tiles and the bottom navigation.
  static const line = Color(0xFFDAE3F7);
}

/// Corner radii taken from the approved mobile design.
abstract final class KoloVibeRadii {
  static const double field = 14;
  static const double tile = 16;
  static const double card = 20;
  static const double pill = 100;
}

/// Text styles from the approved design: Plus Jakarta Sans for display text,
/// Inter for everything else. Sizes are logical pixels and scale with the
/// user's text-size setting.
abstract final class KoloVibeText {
  static TextStyle heading(
    double size, {
    Color color = KoloVibeColors.navy,
    double? height,
  }) =>
      TextStyle(
        fontFamily: 'PlusJakartaSans',
        fontWeight: FontWeight.w800,
        fontSize: size,
        color: color,
        height: height,
      );

  static TextStyle body(
    double size, {
    FontWeight weight = FontWeight.w400,
    Color color = KoloVibeColors.muted,
    double? height,
    double? letterSpacing,
  }) =>
      TextStyle(
        fontFamily: 'Inter',
        fontWeight: weight,
        fontSize: size,
        color: color,
        height: height,
        letterSpacing: letterSpacing,
      );
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
      surface: dark ? const Color(0xFF10264B) : Colors.white,
    );
    final base = ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      fontFamily: 'Inter',
    );
    final ink = dark ? const Color(0xFFE6EDFF) : KoloVibeColors.navy;
    final muted = dark ? const Color(0xFFA8B7D0) : KoloVibeColors.muted;
    final canvas = dark ? KoloVibeColors.deepNavy : KoloVibeColors.lavender;
    final line = dark ? const Color(0xFF223756) : KoloVibeColors.line;
    final fieldBorder = OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: BorderSide(color: line),
    );
    final buttonShape =
        RoundedRectangleBorder(borderRadius: BorderRadius.circular(12));
    final buttonText = KoloVibeText.body(14, weight: FontWeight.w700);
    return base.copyWith(
      scaffoldBackgroundColor: canvas,
      canvasColor: canvas,
      dividerColor: line,
      dividerTheme: DividerThemeData(color: line, thickness: 1, space: 1),
      textTheme: base.textTheme
          .apply(bodyColor: ink, displayColor: ink)
          .copyWith(
            headlineLarge: KoloVibeText.heading(32, color: ink, height: 1.15),
            headlineMedium: KoloVibeText.heading(26, color: ink, height: 1.15),
            headlineSmall: KoloVibeText.heading(22, color: ink, height: 1.2),
            titleLarge: KoloVibeText.heading(18, color: ink),
            titleMedium: KoloVibeText.body(16,
                weight: FontWeight.w600, color: ink, height: 1.3),
            titleSmall: KoloVibeText.body(14,
                weight: FontWeight.w600, color: ink, height: 1.3),
            bodyLarge: KoloVibeText.body(16, color: ink, height: 1.45),
            bodyMedium: KoloVibeText.body(14, color: muted, height: 1.45),
            bodySmall: KoloVibeText.body(12, color: muted, height: 1.4),
            labelLarge: KoloVibeText.body(14, weight: FontWeight.w700),
            labelMedium:
                KoloVibeText.body(12, weight: FontWeight.w600, color: ink),
            labelSmall: KoloVibeText.body(11, color: muted),
          ),
      appBarTheme: AppBarThemeData(
        backgroundColor: canvas,
        foregroundColor: ink,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        toolbarHeight: 56,
        titleSpacing: 16,
        leadingWidth: 44,
        titleTextStyle: KoloVibeText.heading(18, color: ink),
        iconTheme: IconThemeData(color: ink, size: 24),
        actionsIconTheme: IconThemeData(color: ink, size: 24),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: KoloVibeColors.red,
          foregroundColor: Colors.white,
          disabledBackgroundColor: KoloVibeColors.red.withValues(alpha: 0.4),
          disabledForegroundColor: Colors.white70,
          minimumSize: const Size.fromHeight(50),
          shape: buttonShape,
          textStyle: buttonText,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          backgroundColor: dark ? KoloVibeColors.navy : KoloVibeColors.softBlue,
          foregroundColor: ink,
          side: BorderSide.none,
          minimumSize: const Size.fromHeight(50),
          shape: buttonShape,
          textStyle: buttonText,
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: ink,
          minimumSize: const Size(44, 44),
          shape: buttonShape,
          textStyle: KoloVibeText.body(13, weight: FontWeight.w600),
        ),
      ),
      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(
          foregroundColor: ink,
          minimumSize: const Size(44, 44),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surface,
        border: fieldBorder,
        enabledBorder: fieldBorder,
        focusedBorder: fieldBorder.copyWith(
            borderSide: BorderSide(color: ink, width: 1.5)),
        errorBorder: fieldBorder.copyWith(
            borderSide: const BorderSide(color: KoloVibeColors.red)),
        focusedErrorBorder: fieldBorder.copyWith(
            borderSide:
                const BorderSide(color: KoloVibeColors.red, width: 1.5)),
        labelStyle: KoloVibeText.body(14, color: muted),
        floatingLabelStyle:
            KoloVibeText.body(12, weight: FontWeight.w600, color: ink),
        hintStyle: KoloVibeText.body(14, color: muted),
        errorStyle: KoloVibeText.body(12, color: KoloVibeColors.red),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      ),
      cardTheme: CardThemeData(
        color: scheme.surface,
        elevation: 0,
        margin: const EdgeInsets.symmetric(vertical: 4),
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(KoloVibeRadii.tile)),
      ),
      listTileTheme: ListTileThemeData(
        iconColor: muted,
        textColor: ink,
        titleTextStyle:
            KoloVibeText.body(15, weight: FontWeight.w600, color: ink),
        subtitleTextStyle: KoloVibeText.body(12, color: muted, height: 1.4),
        contentPadding: const EdgeInsets.symmetric(horizontal: 4),
        minVerticalPadding: 10,
      ),
      chipTheme: ChipThemeData(
        backgroundColor: scheme.surface,
        selectedColor: KoloVibeColors.navy,
        side: BorderSide(color: line),
        shape: const StadiumBorder(),
        showCheckmark: false,
        labelStyle: KoloVibeText.body(12, weight: FontWeight.w600, color: ink),
        secondaryLabelStyle:
            KoloVibeText.body(12, weight: FontWeight.w600, color: Colors.white),
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 8),
      ),
      checkboxTheme: CheckboxThemeData(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4)),
        side: BorderSide(color: muted, width: 1.5),
        fillColor: WidgetStateProperty.resolveWith((states) =>
            states.contains(WidgetState.selected)
                ? KoloVibeColors.navy
                : Colors.transparent),
      ),
      switchTheme: SwitchThemeData(
        trackColor: WidgetStateProperty.resolveWith((states) =>
            states.contains(WidgetState.selected) ? KoloVibeColors.navy : line),
        thumbColor: const WidgetStatePropertyAll(Colors.white),
        trackOutlineColor: const WidgetStatePropertyAll(Colors.transparent),
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: KoloVibeColors.red,
        linearTrackColor: KoloVibeColors.softBlue,
        circularTrackColor: Colors.transparent,
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: KoloVibeColors.navy,
        contentTextStyle: KoloVibeText.body(13, color: Colors.white),
        actionTextColor: KoloVibeColors.gold,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: scheme.surface,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(KoloVibeRadii.card)),
        titleTextStyle: KoloVibeText.heading(20, color: ink),
        contentTextStyle: KoloVibeText.body(14, color: muted, height: 1.45),
      ),
      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: scheme.surface,
        surfaceTintColor: Colors.transparent,
        showDragHandle: true,
        shape: const RoundedRectangleBorder(
            borderRadius: BorderRadius.vertical(top: Radius.circular(24))),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: scheme.surface,
        indicatorColor: dark ? KoloVibeColors.navy : KoloVibeColors.softBlue,
        height: 76,
      ),
    );
  }
}
