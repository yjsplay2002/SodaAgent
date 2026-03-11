import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

final codeTaskServiceProvider = Provider((_) => const CodeTaskService());

class CodeTaskResponse {
  final String status;
  final int exitCode;
  final String workingDirectory;
  final int durationMs;
  final String resultText;
  final String? stderr;

  const CodeTaskResponse({
    required this.status,
    required this.exitCode,
    required this.workingDirectory,
    required this.durationMs,
    required this.resultText,
    this.stderr,
  });

  bool get isSuccess => status == 'completed' && exitCode == 0;

  factory CodeTaskResponse.fromJson(Map<String, dynamic> json) {
    return CodeTaskResponse(
      status: json['status'] as String? ?? 'failed',
      exitCode: json['exit_code'] as int? ?? -1,
      workingDirectory: json['working_directory'] as String? ?? '.',
      durationMs: json['duration_ms'] as int? ?? 0,
      resultText: json['result_text'] as String? ?? '',
      stderr: json['stderr'] as String?,
    );
  }
}

class CodeTaskException implements Exception {
  final String message;

  const CodeTaskException(this.message);

  @override
  String toString() => message;
}

class CodeTaskService {
  const CodeTaskService();

  Future<CodeTaskResponse> runClaudeTask({
    required String serverUrl,
    required String prompt,
    String workingDirectory = '.',
  }) async {
    final url = Uri.parse('$serverUrl/api/code/claude/run');
    final response = await http
        .post(
          url,
          headers: const {'Content-Type': 'application/json'},
          body: jsonEncode({
            'prompt': prompt,
            'working_directory': workingDirectory,
          }),
        )
        .timeout(const Duration(minutes: 10));

    final body = response.body.trim();
    final decoded = body.isEmpty
        ? <String, dynamic>{}
        : jsonDecode(body) as Map<String, dynamic>;

    if (response.statusCode >= 400) {
      final detail = decoded['detail'];
      throw CodeTaskException(
        detail is String ? detail : 'Claude Code request failed.',
      );
    }

    return CodeTaskResponse.fromJson(decoded);
  }
}
