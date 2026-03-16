import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import 'auth_service.dart';

class BackendSession {
  final String uid;
  final String wsTicket;
  final DateTime expiresAt;

  const BackendSession({
    required this.uid,
    required this.wsTicket,
    required this.expiresAt,
  });

  factory BackendSession.fromJson(Map<String, dynamic> json) {
    return BackendSession(
      uid: json['uid'] as String? ?? '',
      wsTicket: json['ws_ticket'] as String? ?? '',
      expiresAt:
          DateTime.tryParse(json['ws_ticket_expires_at'] as String? ?? '') ??
          DateTime.now(),
    );
  }
}

class BackendSessionService {
  final AuthService _authService;

  const BackendSessionService(this._authService);

  Future<BackendSession> createSession(String serverUrl) async {
    var response = await _postSession(serverUrl);
    if (response.statusCode == 401) {
      response = await _postSession(serverUrl, forceRefresh: true);
    }

    final body = utf8.decode(response.bodyBytes);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw AuthException(_extractMessage(body, response.statusCode));
    }

    final decoded = jsonDecode(body);
    if (decoded is! Map<String, dynamic>) {
      throw const AuthException('Unexpected session response from server.');
    }

    final session = BackendSession.fromJson(decoded);
    if (session.uid.isEmpty || session.wsTicket.isEmpty) {
      throw const AuthException('Server returned an incomplete auth session.');
    }
    return session;
  }

  Future<http.Response> _postSession(
    String serverUrl, {
    bool forceRefresh = false,
  }) async {
    final idToken = await _authService.getIdToken(forceRefresh: forceRefresh);
    return http.post(
      Uri.parse('$serverUrl/api/auth/session'),
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $idToken',
      },
      body: const JsonEncoder().convert({}),
    );
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
    return 'Session request failed with $statusCode.';
  }
}

final backendSessionServiceProvider = Provider<BackendSessionService>((ref) {
  return BackendSessionService(ref.read(authServiceProvider));
});
