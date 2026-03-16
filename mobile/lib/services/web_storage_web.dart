// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use

import 'dart:html' as html;

import 'web_storage.dart';

class BrowserWebStorage implements WebStorage {
  @override
  String? getItem(String key) {
    try {
      return html.window.localStorage[key];
    } catch (_) {
      return null;
    }
  }

  @override
  Future<void> setItem(String key, String value) async {
    try {
      html.window.localStorage[key] = value;
    } catch (_) {}
  }
}

WebStorage buildWebStorage() => BrowserWebStorage();
