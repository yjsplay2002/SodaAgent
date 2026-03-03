import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_sound/flutter_sound.dart';
import 'package:record/record.dart';
/// Handles microphone capture and speaker playback.
///
/// Recording: PCM 16-bit 16kHz mono → Gemini Live API
  /// Playback:  PCM 16-bit 24kHz mono ← Gemini Live API (Aoede female voice)
  class AudioService {
  final AudioRecorder _recorder = AudioRecorder();
  final FlutterSoundPlayer _player = FlutterSoundPlayer();
  StreamSubscription? _recorderSub;
  final _audioController = StreamController<Uint8List>.broadcast();
  bool _isRecording = false;
  bool _playerOpened = false;
  bool _isPlaying = false;
  Stream<Uint8List> get audioStream => _audioController.stream;
  bool get isRecording => _isRecording;
  bool get isPlaying => _isPlaying;
  Future<bool> hasPermission() async {
    return await _recorder.hasPermission();
  }

  // Recording
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

  // Playback
  Future<void> _ensurePlayerOpen() async {
    if (!_playerOpened) {
      await _player.openPlayer();
      _playerOpened = true;
      debugPrint('AudioService: Player opened');
    }
  }
  Future<void> startPlayback({int sampleRate = 24000}) async {
    if (_isPlaying) return;
    await _ensurePlayerOpen();
    await _player.startPlayerFromStream(
      codec: Codec.pcm16,
      interleaved: false,
      numChannels: 1,
      sampleRate: sampleRate,
      bufferSize: 8192,
    );
    _isPlaying = true;
    debugPrint('AudioService: Playback started at ${sampleRate}Hz');
  }
  void feedAudio(Uint8List pcmData) {
    if (!_isPlaying) return;
    _player.uint8ListSink?.add(pcmData);
  }
  Future<void> stopPlayback() async {
    if (!_isPlaying) return;
    try {
      await _player.stopPlayer();
    } catch (_) {}
    _isPlaying = false;
    debugPrint('AudioService: Playback stopped');
  }

  // Lifecycle
  void dispose() {
    stopRecording();
    stopPlayback();
    if (_playerOpened) _player.closePlayer();
    _recorder.dispose();
    _audioController.close();
  }
}
final audioServiceProvider = Provider<AudioService>((ref) {
  final service = AudioService();
  ref.onDispose(() => service.dispose());
  return service;
});
