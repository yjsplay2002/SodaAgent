import 'package:flutter/material.dart';

class SodaTheme {
  static const _bg = Color(0xFF0D1117);
  static const _surface = Color(0xFF161B22);
  static const _card = Color(0xFF21262D);
  static const _accent = Color(0xFF58A6FF);
  static const _accentGlow = Color(0xFF1F6FEB);
  static const _textPrimary = Color(0xFFF0F6FC);
  static const _textSecondary = Color(0xFF8B949E);
  static const _listening = Color(0xFF3FB950);
  static const _error = Color(0xFFF85149);

  static Color get accent => _accent;
  static Color get listening => _listening;
  static Color get error => _error;
  static Color get accentGlow => _accentGlow;

  static ThemeData get dark => ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: _bg,
        colorScheme: const ColorScheme.dark(
          surface: _surface,
          primary: _accent,
          secondary: _accentGlow,
          error: _error,
        ),
        cardColor: _card,
        textTheme: const TextTheme(
          headlineLarge: TextStyle(
            color: _textPrimary,
            fontSize: 28,
            fontWeight: FontWeight.w600,
          ),
          bodyLarge: TextStyle(color: _textPrimary, fontSize: 16),
          bodyMedium: TextStyle(color: _textSecondary, fontSize: 14),
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: _bg,
          elevation: 0,
          centerTitle: true,
          titleTextStyle: TextStyle(
            color: _textPrimary,
            fontSize: 20,
            fontWeight: FontWeight.w500,
          ),
        ),
      );
}
