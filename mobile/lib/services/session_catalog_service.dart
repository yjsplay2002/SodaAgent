import 'dart:convert';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';

class ConversationTurnData {
  final String turnId;
  final String role;
  final String text;
  final String status;
  final bool isFinal;
  final DateTime createdAt;

  ConversationTurnData({
    required this.turnId,
    required this.role,
    required this.text,
    required this.status,
    required this.isFinal,
    required this.createdAt,
  });

  factory ConversationTurnData.fromJson(Map<String, dynamic> json) {
    return ConversationTurnData(
      turnId: json['turn_id'] as String? ?? '',
      role: json['role'] as String? ?? 'assistant',
      text: json['text'] as String? ?? '',
      status: json['status'] as String? ?? 'completed',
      isFinal: json['is_final'] as bool? ?? true,
      createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ??
          DateTime.now(),
    );
  }
}

class ConversationSummary {
  final String conversationId;
  final String title;
  final String preview;
  final String domain;
  final DateTime createdAt;
  final DateTime updatedAt;
  final int turnCount;
  final bool isActive;
  final bool hasBoundSession;

  ConversationSummary({
    required this.conversationId,
    required this.title,
    required this.preview,
    required this.domain,
    required this.createdAt,
    required this.updatedAt,
    required this.turnCount,
    required this.isActive,
    required this.hasBoundSession,
  });

  factory ConversationSummary.fromJson(Map<String, dynamic> json) {
    return ConversationSummary(
      conversationId: json['conversation_id'] as String? ?? '',
      title: json['title'] as String? ?? 'Untitled',
      preview: json['preview'] as String? ?? '',
      domain: json['domain'] as String? ?? 'general',
      createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ??
          DateTime.now(),
      updatedAt: DateTime.tryParse(json['updated_at'] as String? ?? '') ??
          DateTime.now(),
      turnCount: json['turn_count'] as int? ?? 0,
      isActive: json['is_active'] as bool? ?? false,
      hasBoundSession: json['has_bound_session'] as bool? ?? false,
    );
  }
}

class ConversationDetail extends ConversationSummary {
  final List<ConversationTurnData> turns;

  ConversationDetail({
    required super.conversationId,
    required super.title,
    required super.preview,
    required super.domain,
    required super.createdAt,
    required super.updatedAt,
    required super.turnCount,
    required super.isActive,
    required super.hasBoundSession,
    required this.turns,
  });

  factory ConversationDetail.fromJson(Map<String, dynamic> json) {
    return ConversationDetail(
      conversationId: json['conversation_id'] as String? ?? '',
      title: json['title'] as String? ?? 'Untitled',
      preview: json['preview'] as String? ?? '',
      domain: json['domain'] as String? ?? 'general',
      createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ??
          DateTime.now(),
      updatedAt: DateTime.tryParse(json['updated_at'] as String? ?? '') ??
          DateTime.now(),
      turnCount: json['turn_count'] as int? ?? 0,
      isActive: json['is_active'] as bool? ?? false,
      hasBoundSession: json['has_bound_session'] as bool? ?? false,
      turns: ((json['turns'] as List?) ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(ConversationTurnData.fromJson)
          .toList(),
    );
  }
}

class SessionCatalogService {
  Future<List<ConversationSummary>> fetchSessions(
    String serverUrl,
    String userId,
  ) async {
    final payload = await _getJson('$serverUrl/api/sessions/$userId');
    return ((payload['sessions'] as List?) ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(ConversationSummary.fromJson)
        .toList();
  }

  Future<ConversationDetail?> fetchConversation(
    String serverUrl,
    String userId,
    String conversationId,
  ) async {
    try {
      final payload =
          await _getJson('$serverUrl/api/sessions/$userId/$conversationId');
      return ConversationDetail.fromJson(payload);
    } catch (_) {
      return null;
    }
  }

  Future<Map<String, dynamic>> _getJson(String url) async {
    final client = HttpClient();
    try {
      final request = await client.getUrl(Uri.parse(url));
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      final response = await request.close();
      final body = await response.transform(utf8.decoder).join();
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw HttpException(
          'Request failed with ${response.statusCode}',
          uri: Uri.parse(url),
        );
      }
      final decoded = jsonDecode(body);
      if (decoded is Map<String, dynamic>) {
        return decoded;
      }
      throw const FormatException('Unexpected response payload');
    } finally {
      client.close(force: true);
    }
  }
}

final sessionCatalogServiceProvider = Provider<SessionCatalogService>((ref) {
  return SessionCatalogService();
});
