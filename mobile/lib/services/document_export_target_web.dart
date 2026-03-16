// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use

import 'dart:convert';
import 'dart:html' as html;

import 'document_export_target.dart';

class WebDocumentExportTarget implements DocumentExportTarget {
  @override
  Future<String> writeTextFile({
    required String fileName,
    required String content,
  }) async {
    final blob = html.Blob(
      <Object>[utf8.encode(content)],
      'text/plain;charset=utf-8',
    );
    final url = html.Url.createObjectUrlFromBlob(blob);
    final anchor = html.AnchorElement(href: url)
      ..download = fileName
      ..style.display = 'none';

    html.document.body?.append(anchor);
    anchor.click();
    anchor.remove();
    html.Url.revokeObjectUrl(url);
    return fileName;
  }
}

DocumentExportTarget buildDocumentExportTarget() =>
    WebDocumentExportTarget();
