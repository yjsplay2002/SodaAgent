import 'dart:io';
import 'dart:typed_data';

import 'audio_platform.dart';

class IoAudioPlatformAdapter implements AudioPlatformAdapter {
  @override
  bool get isAndroid => Platform.isAndroid;

  @override
  bool get isIOS => Platform.isIOS;

  @override
  bool get shouldPrewarmPlaybackOnUserGesture => false;

  @override
  bool get handlesSavedFilePlayback => false;

  @override
  void prepareForUserGesturePlayback() {}

  @override
  Future<bool> playSavedFile(String path, {void Function()? onFinished}) async {
    return false;
  }

  @override
  Future<void> stopSavedFilePlayback() async {}

  @override
  Future<String?> persistWavBytes(Uint8List wavBytes, String fileName) async {
    try {
      final file = File('${Directory.systemTemp.path}/$fileName');
      await file.writeAsBytes(wavBytes, flush: true);
      return file.path;
    } catch (_) {
      return null;
    }
  }

  @override
  void disposeAllPersistedAudio() {}
}

AudioPlatformAdapter buildAudioPlatformAdapter() => IoAudioPlatformAdapter();
