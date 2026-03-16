import 'package:firebase_core/firebase_core.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/firebase_options.dart';

class FirebaseBootstrapState {
  final bool isSupportedPlatform;
  final bool isConfigured;
  final bool isInitialized;
  final List<String> missingKeys;
  final String? errorMessage;

  const FirebaseBootstrapState({
    required this.isSupportedPlatform,
    required this.isConfigured,
    required this.isInitialized,
    this.missingKeys = const [],
    this.errorMessage,
  });

  const FirebaseBootstrapState.ready()
    : isSupportedPlatform = true,
      isConfigured = true,
      isInitialized = true,
      missingKeys = const [],
      errorMessage = null;

  const FirebaseBootstrapState.unsupported()
    : isSupportedPlatform = false,
      isConfigured = false,
      isInitialized = false,
      missingKeys = const [],
      errorMessage = null;

  const FirebaseBootstrapState.unconfigured(this.missingKeys)
    : isSupportedPlatform = true,
      isConfigured = false,
      isInitialized = false,
      errorMessage = null;

  const FirebaseBootstrapState.failed(String this.errorMessage)
    : isSupportedPlatform = true,
      isConfigured = true,
      isInitialized = false,
      missingKeys = const [];
}

class FirebaseBootstrapService {
  FirebaseBootstrapState? _cachedState;

  Future<FirebaseBootstrapState> ensureInitialized() async {
    final cachedState = _cachedState;
    if (cachedState != null) {
      return cachedState;
    }

    if (!AppFirebaseOptions.isSupportedPlatform) {
      return _cache(const FirebaseBootstrapState.unsupported());
    }

    await AppFirebaseOptions.ensureLoaded();

    final missingKeys = AppFirebaseOptions.missingKeys;
    if (missingKeys.isNotEmpty) {
      return _cache(FirebaseBootstrapState.unconfigured(missingKeys));
    }

    if (Firebase.apps.isNotEmpty) {
      return _cache(const FirebaseBootstrapState.ready());
    }

    try {
      await Firebase.initializeApp(options: AppFirebaseOptions.currentPlatform);
      return _cache(const FirebaseBootstrapState.ready());
    } catch (error) {
      return _cache(FirebaseBootstrapState.failed(error.toString()));
    }
  }

  FirebaseBootstrapState _cache(FirebaseBootstrapState state) {
    _cachedState = state;
    return state;
  }
}

final firebaseBootstrapServiceProvider = Provider<FirebaseBootstrapService>((
  ref,
) {
  return FirebaseBootstrapService();
});

final firebaseBootstrapProvider = FutureProvider<FirebaseBootstrapState>((
  ref,
) async {
  return ref.read(firebaseBootstrapServiceProvider).ensureInitialized();
});
