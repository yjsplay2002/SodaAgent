import 'dart:convert';

import 'auth_service.dart';
import 'web_storage.dart';

class LocalIdentityService {
  static const _storageKey = 'soda_session';
  final AuthService _authService;
  final WebStorage _storage = createWebStorage();

  LocalIdentityService(this._authService);

  Future<Map<String, dynamic>> _readSession() async {
    try {
      final raw = _storage.getItem(_storageKey);
      if (raw == null || raw.isEmpty) return {};
      final decoded = jsonDecode(raw);
      if (decoded is Map<String, dynamic>) {
        return decoded;
      }
    } catch (_) {}
    return {};
  }

  Future<void> _writeSession(Map<String, dynamic> data) async {
    await _storage.setItem(_storageKey, jsonEncode(data));
  }

  Future<String> getOrCreateUserId() async {
    final authenticatedUserId = await _authService.getCurrentUserId();
    final session = await _readSession();
    final userId = session['user_id'] as String?;
    if (userId == authenticatedUserId) {
      return authenticatedUserId;
    }

    session['user_id'] = authenticatedUserId;
    session.remove('conversation_id');
    await _writeSession(session);
    return authenticatedUserId;
  }

  Future<String?> getConversationId() async {
    final userId = await _authService.getCurrentUserId();
    final session = await _readSession();
    if (session['user_id'] != userId) {
      return null;
    }
    final conversationId = session['conversation_id'] as String?;
    if (conversationId == null || conversationId.isEmpty) return null;
    return conversationId;
  }

  Future<void> saveConversationId(String? conversationId) async {
    final userId = await _authService.getCurrentUserId();
    final session = await _readSession();
    session['user_id'] = userId;
    if (conversationId == null || conversationId.isEmpty) {
      session.remove('conversation_id');
    } else {
      session['conversation_id'] = conversationId;
    }
    await _writeSession(session);
  }
}
