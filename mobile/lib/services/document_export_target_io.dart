import 'dart:io';

import 'package:path_provider/path_provider.dart';

import 'document_export_target.dart';

class IoDocumentExportTarget implements DocumentExportTarget {
  @override
  Future<String> writeTextFile({
    required String fileName,
    required String content,
  }) async {
    final directory = await _resolveExportDirectory();
    final file = File('${directory.path}/$fileName');
    await file.writeAsString(content);
    return file.path;
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
}

DocumentExportTarget buildDocumentExportTarget() => IoDocumentExportTarget();
