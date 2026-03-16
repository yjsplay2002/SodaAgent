import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/auth_service.dart';
import '../services/firebase_bootstrap_service.dart';
import 'firebase_setup_screen.dart';
import 'home_screen.dart';
import 'sign_in_screen.dart';

class AppShell extends ConsumerWidget {
  const AppShell({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final bootstrap = ref.watch(firebaseBootstrapProvider);

    return bootstrap.when(
      loading: () => const _StatusScaffold(
        title: 'Starting Soda',
        message: 'Initializing Firebase services...',
      ),
      error: (error, _) => FirebaseSetupScreen(
        title: 'Firebase Startup Failed',
        message: 'Soda could not finish initializing Firebase.',
        detail: error.toString(),
      ),
      data: (state) {
        if (!state.isSupportedPlatform) {
          return const FirebaseSetupScreen(
            title: 'Unsupported Platform',
            message:
                'Firebase Auth is currently configured for Android, iOS, and Web only.',
          );
        }

        if (!state.isConfigured) {
          return FirebaseSetupScreen(
            title: 'Firebase Config Needed',
            message:
                'The app is ready for Google sign-in, but Firebase project values are still missing.',
            missingKeys: state.missingKeys,
          );
        }

        if (!state.isInitialized) {
          return FirebaseSetupScreen(
            title: 'Firebase Initialization Failed',
            message:
                'The app found Firebase settings, but startup still failed.',
            detail: state.errorMessage,
          );
        }

        final authState = ref.watch(authStateProvider);
        return authState.when(
          loading: () => const _StatusScaffold(
            title: 'Checking Session',
            message: 'Restoring your Google sign-in...',
          ),
          error: (error, _) => SignInScreen(errorMessage: error.toString()),
          data: (user) {
            if (user == null) {
              return const SignInScreen();
            }
            return const HomeScreen();
          },
        );
      },
    );
  }
}

class _StatusScaffold extends StatelessWidget {
  final String title;
  final String message;

  const _StatusScaffold({required this.title, required this.message});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const CircularProgressIndicator(),
              const SizedBox(height: 18),
              Text(title, style: Theme.of(context).textTheme.headlineLarge),
              const SizedBox(height: 8),
              Text(message, style: Theme.of(context).textTheme.bodyMedium),
            ],
          ),
        ),
      ),
    );
  }
}
