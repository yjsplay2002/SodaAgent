import 'dart:convert';
import 'dart:io';
import 'dart:math';

class LocalIdentityService {
  static const _fileName = 'soda_session.json';

  Future<File> _sessionFile() async =>
      File('${Directory.systemTemp.path}/$_fileName');

  Future<Map<String, dynamic>> _readSession() async {
    try {
      final file = await _sessionFile();
      if (!await file.exists()) return {};
      final raw = await file.readAsString();
      final decoded = jsonDecode(raw);
      if (decoded is Map<String, dynamic>) {
        return decoded;
      }
    } catch (_) {}
    return {};
  }

  Future<void> _writeSession(Map<String, dynamic> data) async {
    final file = await _sessionFile();
    await file.writeAsString(jsonEncode(data));
  }

  String _newId(String prefix) {
    final random = Random.secure().nextInt(1 << 32).toRadixString(16);
    return '$prefix-${DateTime.now().millisecondsSinceEpoch}-$random';
  }

  Future<String> getOrCreateUserId() async {
    final session = await _readSession();
    final userId = session['user_id'] as String?;
    if (userId != null && userId.isNotEmpty) return userId;

    final newUserId = _newId('user');
    session['user_id'] = newUserId;
    await _writeSession(session);
    return newUserId;
  }

  Future<String?> getConversationId() async {
    final session = await _readSession();
    final conversationId = session['conversation_id'] as String?;
    if (conversationId == null || conversationId.isEmpty) return null;
    return conversationId;
  }

  Future<void> saveConversationId(String? conversationId) async {
    final session = await _readSession();
    if (conversationId == null || conversationId.isEmpty) {
      session.remove('conversation_id');
    } else {
      session['conversation_id'] = conversationId;
    }
    await _writeSession(session);
  }
}
