import 'dart:convert';

import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

class FirebaseConfigMissingException implements Exception {
  final String message;

  const FirebaseConfigMissingException(this.message);

  @override
  String toString() => message;
}

class AppFirebaseOptions {
  const AppFirebaseOptions._();

  static Future<void>? _loadFuture;
  static Map<String, String> _fileValues = const {};

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

  static Future<void> ensureLoaded() {
    final inFlight = _loadFuture;
    if (inFlight != null) {
      return inFlight;
    }

    _loadFuture = _loadFromAsset();
    return _loadFuture!;
  }

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
        'SODA_FIREBASE_WEB_API_KEY': _value(
          _webApiKey,
          'SODA_FIREBASE_WEB_API_KEY',
        ),
        'SODA_FIREBASE_WEB_APP_ID': _value(
          _webAppId,
          'SODA_FIREBASE_WEB_APP_ID',
        ),
        'SODA_FIREBASE_WEB_MESSAGING_SENDER_ID': _value(
          _webMessagingSenderId,
          'SODA_FIREBASE_WEB_MESSAGING_SENDER_ID',
        ),
        'SODA_FIREBASE_WEB_PROJECT_ID': _value(
          _webProjectId,
          'SODA_FIREBASE_WEB_PROJECT_ID',
        ),
        'SODA_FIREBASE_WEB_AUTH_DOMAIN': _value(
          _webAuthDomain,
          'SODA_FIREBASE_WEB_AUTH_DOMAIN',
        ),
      },
      'android' => <String, String>{
        'SODA_FIREBASE_ANDROID_API_KEY': _value(
          _androidApiKey,
          'SODA_FIREBASE_ANDROID_API_KEY',
        ),
        'SODA_FIREBASE_ANDROID_APP_ID': _value(
          _androidAppId,
          'SODA_FIREBASE_ANDROID_APP_ID',
        ),
        'SODA_FIREBASE_ANDROID_MESSAGING_SENDER_ID': _value(
          _androidMessagingSenderId,
          'SODA_FIREBASE_ANDROID_MESSAGING_SENDER_ID',
        ),
        'SODA_FIREBASE_ANDROID_PROJECT_ID': _value(
          _androidProjectId,
          'SODA_FIREBASE_ANDROID_PROJECT_ID',
        ),
      },
      'ios' => <String, String>{
        'SODA_FIREBASE_IOS_API_KEY': _value(
          _iosApiKey,
          'SODA_FIREBASE_IOS_API_KEY',
        ),
        'SODA_FIREBASE_IOS_APP_ID': _value(
          _iosAppId,
          'SODA_FIREBASE_IOS_APP_ID',
        ),
        'SODA_FIREBASE_IOS_MESSAGING_SENDER_ID': _value(
          _iosMessagingSenderId,
          'SODA_FIREBASE_IOS_MESSAGING_SENDER_ID',
        ),
        'SODA_FIREBASE_IOS_PROJECT_ID': _value(
          _iosProjectId,
          'SODA_FIREBASE_IOS_PROJECT_ID',
        ),
        'SODA_FIREBASE_IOS_BUNDLE_ID': _value(
          _iosBundleId,
          'SODA_FIREBASE_IOS_BUNDLE_ID',
        ),
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

    final webApiKey = _value(_webApiKey, 'SODA_FIREBASE_WEB_API_KEY');
    final webAppId = _value(_webAppId, 'SODA_FIREBASE_WEB_APP_ID');
    final webMessagingSenderId = _value(
      _webMessagingSenderId,
      'SODA_FIREBASE_WEB_MESSAGING_SENDER_ID',
    );
    final webProjectId = _value(_webProjectId, 'SODA_FIREBASE_WEB_PROJECT_ID');
    final webAuthDomain = _value(
      _webAuthDomain,
      'SODA_FIREBASE_WEB_AUTH_DOMAIN',
    );
    final webStorageBucket = _value(
      _webStorageBucket,
      'SODA_FIREBASE_WEB_STORAGE_BUCKET',
    );
    final androidApiKey = _value(
      _androidApiKey,
      'SODA_FIREBASE_ANDROID_API_KEY',
    );
    final androidAppId = _value(_androidAppId, 'SODA_FIREBASE_ANDROID_APP_ID');
    final androidMessagingSenderId = _value(
      _androidMessagingSenderId,
      'SODA_FIREBASE_ANDROID_MESSAGING_SENDER_ID',
    );
    final androidProjectId = _value(
      _androidProjectId,
      'SODA_FIREBASE_ANDROID_PROJECT_ID',
    );
    final androidStorageBucket = _value(
      _androidStorageBucket,
      'SODA_FIREBASE_ANDROID_STORAGE_BUCKET',
    );
    final iosApiKey = _value(_iosApiKey, 'SODA_FIREBASE_IOS_API_KEY');
    final iosAppId = _value(_iosAppId, 'SODA_FIREBASE_IOS_APP_ID');
    final iosMessagingSenderId = _value(
      _iosMessagingSenderId,
      'SODA_FIREBASE_IOS_MESSAGING_SENDER_ID',
    );
    final iosProjectId = _value(_iosProjectId, 'SODA_FIREBASE_IOS_PROJECT_ID');
    final iosBundleId = _value(_iosBundleId, 'SODA_FIREBASE_IOS_BUNDLE_ID');
    final iosStorageBucket = _value(
      _iosStorageBucket,
      'SODA_FIREBASE_IOS_STORAGE_BUCKET',
    );

    if (kIsWeb) {
      return FirebaseOptions(
        apiKey: webApiKey,
        appId: webAppId,
        messagingSenderId: webMessagingSenderId,
        projectId: webProjectId,
        authDomain: webAuthDomain,
        storageBucket: webStorageBucket.isEmpty ? null : webStorageBucket,
      );
    }

    return switch (defaultTargetPlatform) {
      TargetPlatform.android => FirebaseOptions(
        apiKey: androidApiKey,
        appId: androidAppId,
        messagingSenderId: androidMessagingSenderId,
        projectId: androidProjectId,
        storageBucket: androidStorageBucket.isEmpty
            ? null
            : androidStorageBucket,
      ),
      TargetPlatform.iOS => FirebaseOptions(
        apiKey: iosApiKey,
        appId: iosAppId,
        messagingSenderId: iosMessagingSenderId,
        projectId: iosProjectId,
        iosBundleId: iosBundleId,
        storageBucket: iosStorageBucket.isEmpty ? null : iosStorageBucket,
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
      TargetPlatform.iOS => _value(
        _iosGoogleClientId,
        'SODA_GOOGLE_IOS_CLIENT_ID',
      ),
      _ => '',
    };
    return clientId.trim().isEmpty ? null : clientId;
  }

  static String? get googleServerClientId =>
      _value(
        _googleServerClientId,
        'SODA_GOOGLE_SERVER_CLIENT_ID',
      ).trim().isEmpty
      ? null
      : _value(_googleServerClientId, 'SODA_GOOGLE_SERVER_CLIENT_ID');

  static Future<void> _loadFromAsset() async {
    try {
      final rawConfig = await rootBundle.loadString('firebase_config.json');
      final decoded = jsonDecode(rawConfig);
      if (decoded is Map<String, dynamic>) {
        _fileValues = decoded.map(
          (key, value) => MapEntry(key, value?.toString() ?? ''),
        );
      }
    } catch (_) {
      _fileValues = const {};
    }
  }

  static String _value(String environmentValue, String key) {
    final trimmedEnvironmentValue = environmentValue.trim();
    if (trimmedEnvironmentValue.isNotEmpty) {
      return trimmedEnvironmentValue;
    }

    return (_fileValues[key] ?? '').trim();
  }

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
