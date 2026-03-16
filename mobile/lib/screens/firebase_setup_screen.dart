import 'package:flutter/material.dart';

import '../app/theme.dart';

class FirebaseSetupScreen extends StatelessWidget {
  final String title;
  final String message;
  final List<String> missingKeys;
  final String? detail;

  const FirebaseSetupScreen({
    super.key,
    required this.title,
    required this.message,
    this.missingKeys = const [],
    this.detail,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 520),
              child: Container(
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.05),
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(
                    color: Colors.white.withValues(alpha: 0.08),
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: Theme.of(context).textTheme.headlineLarge,
                    ),
                    const SizedBox(height: 12),
                    Text(message, style: Theme.of(context).textTheme.bodyLarge),
                    if (missingKeys.isNotEmpty) ...[
                      const SizedBox(height: 20),
                      Text(
                        'Missing dart-defines',
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.72),
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 10),
                      for (final key in missingKeys)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: Text(
                            key,
                            style: TextStyle(
                              color: Colors.white.withValues(alpha: 0.88),
                              fontFamily: 'monospace',
                            ),
                          ),
                        ),
                    ],
                    if (detail != null && detail!.trim().isNotEmpty) ...[
                      const SizedBox(height: 20),
                      Text(
                        detail!,
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.62),
                        ),
                      ),
                    ],
                    const SizedBox(height: 20),
                    Text(
                      'Use `mobile/firebase_config.example.json` as the template for your real Firebase config file.',
                      style: TextStyle(
                        color: SodaTheme.accent.withValues(alpha: 0.9),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
