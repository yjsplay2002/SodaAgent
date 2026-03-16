import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart';

class FirebaseConfigMissingException implements Exception {
  final String message;

  const FirebaseConfigMissingException(this.message);

  @override
  String toString() => message;
}

class AppFirebaseOptions {
  const AppFirebaseOptions._();

  static const _webApiKey = String.fromEnvironment('SODA_FIREBASE_WEB_API_KEY');
  static const _webAppId = String.fromEnvironment('SODA_FIREBASE_WEB_APP_ID');
  static const _webMessagingSenderId = String.fromEnvironment(
    'SODA_FIREBASE_WEB_MESSAGING_SENDER_ID',
  );
  static const _webProjectId = String.fromEnvironment(
    'SODA_FIREBASE_WEB_PROJECT_ID',
  );
  static const _webAuthDomain = String.fromEnvironment(
    'SODA_FIREBASE_WEB_AUTH_DOMAIN',
  );
  static const _webStorageBucket = String.fromEnvironment(
    'SODA_FIREBASE_WEB_STORAGE_BUCKET',
  );

  static const _androidApiKey = String.fromEnvironment(
    'SODA_FIREBASE_ANDROID_API_KEY',
  );
  static const _androidAppId = String.fromEnvironment(
    'SODA_FIREBASE_ANDROID_APP_ID',
  );
  static const _androidMessagingSenderId = String.fromEnvironment(
    'SODA_FIREBASE_ANDROID_MESSAGING_SENDER_ID',
  );
  static const _androidProjectId = String.fromEnvironment(
    'SODA_FIREBASE_ANDROID_PROJECT_ID',
  );
  static const _androidStorageBucket = String.fromEnvironment(
    'SODA_FIREBASE_ANDROID_STORAGE_BUCKET',
  );

  static const _iosApiKey = String.fromEnvironment('SODA_FIREBASE_IOS_API_KEY');
  static const _iosAppId = String.fromEnvironment('SODA_FIREBASE_IOS_APP_ID');
  static const _iosMessagingSenderId = String.fromEnvironment(
    'SODA_FIREBASE_IOS_MESSAGING_SENDER_ID',
  );
  static const _iosProjectId = String.fromEnvironment(
    'SODA_FIREBASE_IOS_PROJECT_ID',
  );
  static const _iosBundleId = String.fromEnvironment(
    'SODA_FIREBASE_IOS_BUNDLE_ID',
  );
  static const _iosStorageBucket = String.fromEnvironment(
    'SODA_FIREBASE_IOS_STORAGE_BUCKET',
  );
  static const _iosGoogleClientId = String.fromEnvironment(
    'SODA_GOOGLE_IOS_CLIENT_ID',
  );

  static const _googleServerClientId = String.fromEnvironment(
    'SODA_GOOGLE_SERVER_CLIENT_ID',
  );

  static bool get isSupportedPlatform {
    if (kIsWeb) {
      return true;
    }

    return switch (defaultTargetPlatform) {
      TargetPlatform.android || TargetPlatform.iOS => true,
      _ => false,
    };
  }

  static List<String> get missingKeys {
    if (!isSupportedPlatform) {
      return const [];
    }

    final fields = switch (_platformKey) {
      'web' => <String, String>{
        'SODA_FIREBASE_WEB_API_KEY': _webApiKey,
        'SODA_FIREBASE_WEB_APP_ID': _webAppId,
        'SODA_FIREBASE_WEB_MESSAGING_SENDER_ID': _webMessagingSenderId,
        'SODA_FIREBASE_WEB_PROJECT_ID': _webProjectId,
        'SODA_FIREBASE_WEB_AUTH_DOMAIN': _webAuthDomain,
      },
      'android' => <String, String>{
        'SODA_FIREBASE_ANDROID_API_KEY': _androidApiKey,
        'SODA_FIREBASE_ANDROID_APP_ID': _androidAppId,
        'SODA_FIREBASE_ANDROID_MESSAGING_SENDER_ID': _androidMessagingSenderId,
        'SODA_FIREBASE_ANDROID_PROJECT_ID': _androidProjectId,
      },
      'ios' => <String, String>{
        'SODA_FIREBASE_IOS_API_KEY': _iosApiKey,
        'SODA_FIREBASE_IOS_APP_ID': _iosAppId,
        'SODA_FIREBASE_IOS_MESSAGING_SENDER_ID': _iosMessagingSenderId,
        'SODA_FIREBASE_IOS_PROJECT_ID': _iosProjectId,
        'SODA_FIREBASE_IOS_BUNDLE_ID': _iosBundleId,
      },
      _ => const <String, String>{},
    };

    return fields.entries
        .where((entry) => entry.value.trim().isEmpty)
        .map((entry) => entry.key)
        .toList(growable: false);
  }

  static bool get isConfigured => isSupportedPlatform && missingKeys.isEmpty;

  static FirebaseOptions get currentPlatform {
    if (!isSupportedPlatform) {
      throw const FirebaseConfigMissingException(
        'Firebase auth is only configured for Android, iOS, and Web.',
      );
    }

    final missing = missingKeys;
    if (missing.isNotEmpty) {
      throw FirebaseConfigMissingException(
        'Missing Firebase configuration: ${missing.join(', ')}',
      );
    }

    if (kIsWeb) {
      return FirebaseOptions(
        apiKey: _webApiKey,
        appId: _webAppId,
        messagingSenderId: _webMessagingSenderId,
        projectId: _webProjectId,
        authDomain: _webAuthDomain,
        storageBucket: _webStorageBucket.isEmpty ? null : _webStorageBucket,
      );
    }

    return switch (defaultTargetPlatform) {
      TargetPlatform.android => FirebaseOptions(
        apiKey: _androidApiKey,
        appId: _androidAppId,
        messagingSenderId: _androidMessagingSenderId,
        projectId: _androidProjectId,
        storageBucket: _androidStorageBucket.isEmpty
            ? null
            : _androidStorageBucket,
      ),
      TargetPlatform.iOS => FirebaseOptions(
        apiKey: _iosApiKey,
        appId: _iosAppId,
        messagingSenderId: _iosMessagingSenderId,
        projectId: _iosProjectId,
        iosBundleId: _iosBundleId,
        storageBucket: _iosStorageBucket.isEmpty ? null : _iosStorageBucket,
      ),
      _ => throw const FirebaseConfigMissingException(
        'Firebase auth is only configured for Android, iOS, and Web.',
      ),
    };
  }

  static String? get googleClientId {
    if (kIsWeb) {
      return null;
    }

    final clientId = switch (defaultTargetPlatform) {
      TargetPlatform.iOS => _iosGoogleClientId,
      _ => '',
    };
    return clientId.trim().isEmpty ? null : clientId;
  }

  static String? get googleServerClientId =>
      _googleServerClientId.trim().isEmpty ? null : _googleServerClientId;

  static String get _platformKey {
    if (kIsWeb) {
      return 'web';
    }

    return switch (defaultTargetPlatform) {
      TargetPlatform.android => 'android',
      TargetPlatform.iOS => 'ios',
      _ => 'unsupported',
    };
  }
}
