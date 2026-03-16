import 'document_export_target_io.dart'
    if (dart.library.html) 'document_export_target_web.dart';

abstract class DocumentExportTarget {
  Future<String> writeTextFile({
    required String fileName,
    required String content,
  });
}

DocumentExportTarget createDocumentExportTarget() => buildDocumentExportTarget();
