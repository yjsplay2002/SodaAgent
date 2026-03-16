import 'dart:io';

import 'web_storage.dart';

class FileWebStorage implements WebStorage {
  Future<File> _fileForKey(String key) async =>
      File('${Directory.systemTemp.path}/$key.json');

  @override
  String? getItem(String key) {
    try {
      final file = File('${Directory.systemTemp.path}/$key.json');
      if (!file.existsSync()) {
        return null;
      }
      return file.readAsStringSync();
    } catch (_) {
      return null;
    }
  }

  @override
  Future<void> setItem(String key, String value) async {
    final file = await _fileForKey(key);
    await file.writeAsString(value);
  }
}

WebStorage buildWebStorage() => FileWebStorage();
