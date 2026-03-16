import 'dart:typed_data';

import 'audio_platform_io.dart' if (dart.library.html) 'audio_platform_web.dart';

abstract class AudioPlatformAdapter {
  bool get isAndroid;

  bool get isIOS;

  bool get shouldPrewarmPlaybackOnUserGesture;

  bool get handlesSavedFilePlayback;

  void prepareForUserGesturePlayback();

  Future<bool> playSavedFile(String path, {void Function()? onFinished});

  Future<void> stopSavedFilePlayback();

  Future<String?> persistWavBytes(Uint8List wavBytes, String fileName);

  void disposeAllPersistedAudio();
}

AudioPlatformAdapter createAudioPlatformAdapter() => buildAudioPlatformAdapter();
