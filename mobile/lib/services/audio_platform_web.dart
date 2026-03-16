// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use

import 'dart:async';
import 'dart:html' as html;
import 'dart:typed_data';

import 'audio_platform.dart';

class WebAudioPlatformAdapter implements AudioPlatformAdapter {
  static const String _silentWavDataUri =
      'data:audio/wav;base64,'
      'UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA';

  final Set<String> _objectUrls = <String>{};
  html.AudioElement? _unlockAudio;
  html.AudioElement? _savedAudio;
  StreamSubscription<html.Event>? _savedAudioEndedSubscription;
  bool _playbackUnlocked = false;

  @override
  bool get isAndroid => false;

  @override
  bool get isIOS => false;

  @override
  bool get shouldPrewarmPlaybackOnUserGesture => true;

  @override
  bool get handlesSavedFilePlayback => true;

  @override
  void prepareForUserGesturePlayback() {
    if (_playbackUnlocked) {
      return;
    }

    final audio = _unlockAudio ??=
        (html.AudioElement()
          ..src = _silentWavDataUri
          ..preload = 'auto'
          ..volume = 0
          ..setAttribute('playsinline', 'true'));

    unawaited(
      audio.play().then((_) {
        audio.pause();
        audio.currentTime = 0;
        _playbackUnlocked = true;
      }).catchError((Object error) {
        html.window.console.warn('Audio unlock failed: $error');
      }),
    );
  }

  @override
  Future<bool> playSavedFile(
    String path, {
    void Function()? onFinished,
  }) async {
    await stopSavedFilePlayback();
    prepareForUserGesturePlayback();

    final audio = html.AudioElement()
      ..src = path
      ..preload = 'auto'
      ..volume = 1
      ..setAttribute('playsinline', 'true');

    _savedAudio = audio;
    _savedAudioEndedSubscription = audio.onEnded.listen((_) {
      onFinished?.call();
    });

    try {
      await audio.play();
      return true;
    } catch (error) {
      html.window.console.warn('Saved audio playback failed: $error');
      await stopSavedFilePlayback();
      return false;
    }
  }

  @override
  Future<void> stopSavedFilePlayback() async {
    await _savedAudioEndedSubscription?.cancel();
    _savedAudioEndedSubscription = null;
    _savedAudio?.pause();
    _savedAudio = null;
  }

  @override
  Future<String?> persistWavBytes(Uint8List wavBytes, String fileName) async {
    final blob = html.Blob(<Object>[wavBytes], 'audio/wav');
    final url = html.Url.createObjectUrlFromBlob(blob);
    _objectUrls.add(url);
    return url;
  }

  @override
  void disposeAllPersistedAudio() {
    _unlockAudio?.pause();
    _unlockAudio = null;
    _savedAudioEndedSubscription?.cancel();
    _savedAudioEndedSubscription = null;
    _savedAudio?.pause();
    _savedAudio = null;
    for (final url in _objectUrls) {
      html.Url.revokeObjectUrl(url);
    }
    _objectUrls.clear();
  }
}

AudioPlatformAdapter buildAudioPlatformAdapter() => WebAudioPlatformAdapter();
