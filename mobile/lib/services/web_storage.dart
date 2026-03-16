import 'web_storage_io.dart' if (dart.library.html) 'web_storage_web.dart';

abstract class WebStorage {
  String? getItem(String key);

  Future<void> setItem(String key, String value);
}

WebStorage createWebStorage() => buildWebStorage();
