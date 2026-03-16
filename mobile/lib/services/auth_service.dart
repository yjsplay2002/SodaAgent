import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_sign_in/google_sign_in.dart';

import '../config/firebase_options.dart';

class AuthException implements Exception {
  final String message;

  const AuthException(this.message);

  @override
  String toString() => message;
}

class AuthService {
  bool _googleInitialized = false;

  FirebaseAuth get _firebaseAuth => FirebaseAuth.instance;

  Stream<User?> authStateChanges() => _firebaseAuth.authStateChanges();

  User? get currentUser => _firebaseAuth.currentUser;

  Future<UserCredential> signInWithGoogle() async {
    try {
      if (kIsWeb) {
        final provider = GoogleAuthProvider()
          ..addScope('email')
          ..setCustomParameters(const {'prompt': 'select_account'});
        return await _firebaseAuth.signInWithPopup(provider);
      }

      await _ensureGoogleInitialized();
      final googleUser = await GoogleSignIn.instance.authenticate();
      final googleAuth = googleUser.authentication;
      final idToken = googleAuth.idToken;
      if (idToken == null || idToken.isEmpty) {
        throw const AuthException('Google sign-in did not return an ID token.');
      }

      final credential = GoogleAuthProvider.credential(idToken: idToken);
      return await _firebaseAuth.signInWithCredential(credential);
    } on GoogleSignInException catch (error) {
      throw AuthException(_googleSignInErrorMessage(error));
    } on FirebaseAuthException catch (error) {
      throw AuthException(error.message ?? 'Firebase authentication failed.');
    } on AuthException {
      rethrow;
    } catch (error) {
      throw AuthException('Google sign-in failed: $error');
    }
  }

  Future<String> getIdToken({bool forceRefresh = false}) async {
    final user = currentUser;
    if (user == null) {
      throw const AuthException('Please sign in first.');
    }

    final token = await user.getIdToken(forceRefresh);
    if (token == null || token.isEmpty) {
      throw const AuthException('Unable to obtain a Firebase ID token.');
    }
    return token;
  }

  Future<String> getCurrentUserId() async {
    final user = currentUser;
    if (user == null) {
      throw const AuthException('Please sign in first.');
    }
    return user.uid;
  }

  Future<void> signOut() async {
    if (!kIsWeb) {
      try {
        await GoogleSignIn.instance.disconnect();
      } catch (_) {}
    }
    await _firebaseAuth.signOut();
  }

  Future<void> _ensureGoogleInitialized() async {
    if (_googleInitialized) {
      return;
    }

    await AppFirebaseOptions.ensureLoaded();

    await GoogleSignIn.instance.initialize(
      clientId: AppFirebaseOptions.googleClientId,
      serverClientId: AppFirebaseOptions.googleServerClientId,
    );
    _googleInitialized = true;
  }

  String _googleSignInErrorMessage(GoogleSignInException error) {
    return switch (error.code) {
      GoogleSignInExceptionCode.canceled => 'Google sign-in was canceled.',
      GoogleSignInExceptionCode.clientConfigurationError =>
        'Google sign-in client configuration is incomplete.',
      GoogleSignInExceptionCode.uiUnavailable =>
        'Google sign-in UI is unavailable on this device.',
      GoogleSignInExceptionCode.userMismatch =>
        'Please finish signing out before switching Google accounts.',
      _ => error.description ?? 'Google sign-in failed.',
    };
  }
}

final authServiceProvider = Provider<AuthService>((ref) {
  return AuthService();
});

final authStateProvider = StreamProvider<User?>((ref) {
  return ref.read(authServiceProvider).authStateChanges();
});
