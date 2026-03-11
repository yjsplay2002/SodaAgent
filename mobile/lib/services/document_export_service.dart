import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';

import 'voice_session.dart';

final documentExportServiceProvider = Provider(
  (_) => const DocumentExportService(),
);

class ExportedDocument {
  final String fileName;
  final String path;

  const ExportedDocument({required this.fileName, required this.path});
}

class DocumentExportException implements Exception {
  final String message;

  const DocumentExportException(this.message);

  @override
  String toString() => message;
}

class DocumentExportService {
  const DocumentExportService();

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
    final directory = await _resolveExportDirectory();
    final file = File('${directory.path}/$fileName');

    await file.writeAsString(
      _buildMarkdown(
        entries: entries,
        conversationId: conversationId,
        exportedAt: now,
      ),
    );

    return ExportedDocument(fileName: fileName, path: file.path);
  }

  Future<Directory> _resolveExportDirectory() async {
    try {
      final downloads = await getDownloadsDirectory();
      if (downloads != null) {
        await downloads.create(recursive: true);
        return downloads;
      }
    } catch (_) {}

    final documents = await getApplicationDocumentsDirectory();
    await documents.create(recursive: true);
    return documents;
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
