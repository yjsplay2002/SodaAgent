import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'document_export_target.dart';
import 'voice_session.dart';

final documentExportServiceProvider = Provider(
  (_) => DocumentExportService(),
);

class ExportedDocument {
  final String fileName;
  final String path;
  final String content;

  const ExportedDocument({
    required this.fileName,
    required this.path,
    required this.content,
  });
}

class DocumentExportException implements Exception {
  final String message;

  const DocumentExportException(this.message);

  @override
  String toString() => message;
}

class DocumentExportService {
  DocumentExportService({DocumentExportTarget? target})
    : _target = target ?? createDocumentExportTarget();

  final DocumentExportTarget _target;

  Future<ExportedDocument> exportConversationAsText({
    required List<TranscriptEntry> transcripts,
    String? conversationId,
  }) async {
    final entries = transcripts
        .where((entry) => entry.text.trim().isNotEmpty)
        .toList(growable: false);
    if (entries.isEmpty) {
      throw const DocumentExportException('No conversation to export yet.');
    }

    final now = DateTime.now();
    final fileName = 'soda_conversation_${_fileTimestamp(now)}.txt';
    final content = _buildMarkdown(
      entries: entries,
      conversationId: conversationId,
      exportedAt: now,
    );

    final path = await _target.writeTextFile(fileName: fileName, content: content);
    await Clipboard.setData(ClipboardData(text: content));

    return ExportedDocument(fileName: fileName, path: path, content: content);
  }

  Future<ExportedDocument> exportResponseAsText({
    required TranscriptEntry entry,
    String? conversationId,
  }) async {
    if (entry.text.trim().isEmpty) {
      throw const DocumentExportException('No response text to export.');
    }

    final now = DateTime.now();
    final fileName = 'soda_response_${_fileTimestamp(now)}.txt';
    final content = _buildResponseMarkdown(
      entry: entry,
      conversationId: conversationId,
      exportedAt: now,
    );

    final path = await _target.writeTextFile(fileName: fileName, content: content);
    await Clipboard.setData(ClipboardData(text: entry.text.trim()));

    return ExportedDocument(fileName: fileName, path: path, content: content);
  }

  String _buildMarkdown({
    required List<TranscriptEntry> entries,
    required DateTime exportedAt,
    String? conversationId,
  }) {
    final buffer = StringBuffer()
      ..writeln('# Soda Conversation Export')
      ..writeln()
      ..writeln('- Exported at: ${exportedAt.toIso8601String()}')
      ..writeln(
        '- Conversation ID: ${conversationId?.trim().isNotEmpty == true ? conversationId!.trim() : 'not available'}',
      )
      ..writeln('- Message count: ${entries.length}')
      ..writeln();

    for (final entry in entries) {
      buffer
        ..writeln('## ${_roleLabel(entry.role)}')
        ..writeln()
        ..writeln('- Timestamp: ${entry.timestamp.toIso8601String()}')
        ..writeln('- Final: ${entry.isFinal ? 'yes' : 'no'}')
        ..writeln('- Interrupted: ${entry.isInterrupted ? 'yes' : 'no'}')
        ..writeln()
        ..writeln(entry.text.trim())
        ..writeln();
    }

    return buffer.toString();
  }

  String _buildResponseMarkdown({
    required TranscriptEntry entry,
    required DateTime exportedAt,
    String? conversationId,
  }) {
    final buffer = StringBuffer()
      ..writeln('# Soda Response Export')
      ..writeln()
      ..writeln('- Exported at: ${exportedAt.toIso8601String()}')
      ..writeln(
        '- Conversation ID: ${conversationId?.trim().isNotEmpty == true ? conversationId!.trim() : 'not available'}',
      )
      ..writeln('- Role: ${_roleLabel(entry.role)}')
      ..writeln('- Timestamp: ${entry.timestamp.toIso8601String()}')
      ..writeln()
      ..writeln(entry.text.trim());
    return buffer.toString();
  }

  String _roleLabel(String role) {
    switch (role) {
      case 'user':
        return 'User';
      case 'assistant':
      case 'model':
        return 'Assistant';
      case 'system':
        return 'System';
      default:
        return role;
    }
  }

  String _fileTimestamp(DateTime value) {
    final yyyy = value.year.toString().padLeft(4, '0');
    final mm = value.month.toString().padLeft(2, '0');
    final dd = value.day.toString().padLeft(2, '0');
    final hh = value.hour.toString().padLeft(2, '0');
    final min = value.minute.toString().padLeft(2, '0');
    final sec = value.second.toString().padLeft(2, '0');
    return '$yyyy$mm${dd}_$hh$min$sec';
  }
}
