import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:record/record.dart';

/// Handles microphone capture using the `record` package.
/// Streams raw PCM 16-bit 16kHz mono audio for Gemini Live API.
class AudioService {
  final AudioRecorder _recorder = AudioRecorder();
  StreamSubscription? _recorderSub;
  final _audioController = StreamController<Uint8List>.broadcast();
  bool _isRecording = false;

  Stream<Uint8List> get audioStream => _audioController.stream;
  bool get isRecording => _isRecording;

  Future<bool> hasPermission() async {
    return await _recorder.hasPermission();
  }

  /// Start streaming microphone audio as PCM 16kHz 16-bit mono.
  Future<bool> startRecording() async {
    if (_isRecording) return true;

    final hasPerms = await _recorder.hasPermission();
    if (!hasPerms) return false;

    try {
      final stream = await _recorder.startStream(
        const RecordConfig(
          encoder: AudioEncoder.pcm16bits,
          sampleRate: 16000,
          numChannels: 1,
          autoGain: true,
          echoCancel: true,
          noiseSuppress: true,
        ),
      );

      _recorderSub = stream.listen((data) {
        _audioController.add(data);
      });

      _isRecording = true;
      return true;
    } catch (e) {
      debugPrint('AudioService: startRecording failed: $e');
      _isRecording = false;
      return false;
    }
  }

  Future<void> stopRecording() async {
    if (!_isRecording) return;
    await _recorderSub?.cancel();
    _recorderSub = null;
    try {
      await _recorder.stop();
    } catch (_) {}
    _isRecording = false;
  }

  void dispose() {
    stopRecording();
    _recorder.dispose();
    _audioController.close();
  }
}

final audioServiceProvider = Provider<AudioService>((ref) {
  final service = AudioService();
  ref.onDispose(() => service.dispose());
  return service;
});
