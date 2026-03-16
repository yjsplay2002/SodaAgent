import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import 'auth_service.dart';

class BackendUserProfile {
  final String uid;
  final String? email;
  final String? displayName;
  final String? photoUrl;
  final String? phoneNumber;

  const BackendUserProfile({
    required this.uid,
    this.email,
    this.displayName,
    this.photoUrl,
    this.phoneNumber,
  });

  factory BackendUserProfile.fromJson(Map<String, dynamic> json) {
    return BackendUserProfile(
      uid: json['uid'] as String? ?? '',
      email: json['email'] as String?,
      displayName: json['display_name'] as String?,
      photoUrl: json['photo_url'] as String?,
      phoneNumber: json['phone_number'] as String?,
    );
  }
}

class BackendUserProfileService {
  final AuthService _authService;

  const BackendUserProfileService(this._authService);

  Future<BackendUserProfile> fetchProfile(String serverUrl) async {
    var response = await _getProfile(serverUrl);
    if (response.statusCode == 401) {
      response = await _getProfile(serverUrl, forceRefresh: true);
    }
    return _parseProfileResponse(response);
  }

  Future<BackendUserProfile> updatePhoneNumber(
    String serverUrl, {
    String? phoneNumber,
  }) async {
    var response = await _patchProfile(serverUrl, phoneNumber: phoneNumber);
    if (response.statusCode == 401) {
      response = await _patchProfile(
        serverUrl,
        phoneNumber: phoneNumber,
        forceRefresh: true,
      );
    }
    return _parseProfileResponse(response);
  }

  Future<http.Response> _getProfile(
    String serverUrl, {
    bool forceRefresh = false,
  }) async {
    final idToken = await _authService.getIdToken(forceRefresh: forceRefresh);
    return http.get(
      Uri.parse('$serverUrl/api/auth/profile'),
      headers: {
        'Accept': 'application/json',
        'Authorization': 'Bearer $idToken',
      },
    );
  }

  Future<http.Response> _patchProfile(
    String serverUrl, {
    String? phoneNumber,
    bool forceRefresh = false,
  }) async {
    final idToken = await _authService.getIdToken(forceRefresh: forceRefresh);
    return http.patch(
      Uri.parse('$serverUrl/api/auth/profile'),
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $idToken',
      },
      body: jsonEncode({'phone_number': phoneNumber}),
    );
  }

  BackendUserProfile _parseProfileResponse(http.Response response) {
    final body = utf8.decode(response.bodyBytes);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw AuthException(_extractMessage(body, response.statusCode));
    }

    final decoded = jsonDecode(body);
    if (decoded is! Map<String, dynamic>) {
      throw const AuthException('Unexpected user profile response from server.');
    }

    final profile = BackendUserProfile.fromJson(decoded);
    if (profile.uid.isEmpty) {
      throw const AuthException('Server returned an incomplete user profile.');
    }
    return profile;
  }

  String _extractMessage(String body, int statusCode) {
    try {
      final decoded = jsonDecode(body);
      if (decoded is Map<String, dynamic>) {
        final detail = decoded['detail'];
        if (detail is String && detail.trim().isNotEmpty) {
          return detail;
        }
      }
    } catch (_) {}
    return 'Profile request failed with $statusCode.';
  }
}

final backendUserProfileServiceProvider = Provider<BackendUserProfileService>((
  ref,
) {
  return BackendUserProfileService(ref.read(authServiceProvider));
});
