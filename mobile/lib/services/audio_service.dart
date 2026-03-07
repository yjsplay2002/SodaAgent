import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_sound/flutter_sound.dart';
import 'package:logger/logger.dart';
import 'package:record/record.dart';

/// Handles microphone capture, speaker playback, and audio file operations.
///
/// Recording: PCM 16-bit 16kHz mono → Gemini Live API
/// Playback:  PCM 16-bit 24kHz mono ← Gemini Live API (Aoede female voice)
class AudioService {
  AudioRecorder? _recorder;
  FlutterSoundPlayer? _player;
  FlutterSoundPlayer? _filePlayer;

  StreamSubscription? _recorderSub;
  final _audioController = StreamController<Uint8List>.broadcast();

  bool _isRecording = false;
  bool _playerOpened = false;
  bool _isPlaying = false;
  bool _filePlayerOpened = false;
  String? currentlyPlayingFile;
  double _liveVolume = 1.0;

  Stream<Uint8List> get audioStream => _audioController.stream;
  bool get isRecording => _isRecording;
  bool get isPlaying => _isPlaying;

  AudioRecorder get _recorderInstance => _recorder ??= AudioRecorder();

  FlutterSoundPlayer get _livePlayer =>
      _player ??= FlutterSoundPlayer(logLevel: Level.error);

  FlutterSoundPlayer get _savedFilePlayer =>
      _filePlayer ??= FlutterSoundPlayer(logLevel: Level.error);

  Future<bool> hasPermission() async {
    return await _recorderInstance.hasPermission();
  }

  // ─── Recording ───

  Future<bool> startRecording() async {
    if (_isRecording) return true;
    final recorder = _recorderInstance;
    final hasPerms = await recorder.hasPermission();
    if (!hasPerms) return false;
    try {
      final stream = await recorder.startStream(
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
      await _recorder?.stop();
    } catch (_) {}
    _isRecording = false;
  }

  // ─── Live Stream Playback ───

  Future<void> _ensurePlayerOpen() async {
    if (!_playerOpened) {
      await _livePlayer.openPlayer();
      _playerOpened = true;
      debugPrint('AudioService: Player opened');
    }
  }

  Future<void> startPlayback({int sampleRate = 24000}) async {
    if (_isPlaying) return;
    await _ensurePlayerOpen();
    await _livePlayer.startPlayerFromStream(
      codec: Codec.pcm16,
      interleaved: false,
      numChannels: 1,
      sampleRate: sampleRate,
      bufferSize: 8192,
    );
    await _livePlayer.setVolume(_liveVolume);
    _isPlaying = true;
    debugPrint('AudioService: Playback started at ${sampleRate}Hz');
  }

  void feedAudio(Uint8List pcmData) {
    if (!_isPlaying) return;
    _livePlayer.uint8ListSink?.add(pcmData);
  }

  Future<void> stopPlayback() async {
    if (!_isPlaying) return;
    try {
      await _player?.stopPlayer();
    } catch (_) {}
    _isPlaying = false;
    debugPrint('AudioService: Playback stopped');
  }

  Future<void> duckPlayback({double volume = 0.2}) async {
    _liveVolume = volume.clamp(0.0, 1.0);
    if (!_playerOpened) return;
    try {
      await _player?.setVolume(_liveVolume);
    } catch (_) {}
  }

  Future<void> restorePlaybackVolume() async {
    _liveVolume = 1.0;
    if (!_playerOpened) return;
    try {
      await _player?.setVolume(_liveVolume);
    } catch (_) {}
  }

  // ─── WAV File Save ───

  /// Save PCM chunks as a WAV file. Returns file path or null on error.
  Future<String?> saveWavFile(
    List<Uint8List> pcmChunks, {
    int sampleRate = 24000,
  }) async {
    if (pcmChunks.isEmpty) return null;
    try {
      final path =
          '${Directory.systemTemp.path}/soda_${DateTime.now().millisecondsSinceEpoch}.wav';

      int dataSize = 0;
      for (final chunk in pcmChunks) {
        dataSize += chunk.length;
      }

      final file = File(path);
      final sink = file.openWrite();
      sink.add(_wavHeader(dataSize, sampleRate));
      for (final chunk in pcmChunks) {
        sink.add(chunk);
      }
      await sink.close();

      debugPrint('AudioService: Saved WAV ${dataSize}b -> $path');
      return path;
    } catch (e) {
      debugPrint('AudioService: saveWavFile error: $e');
      return null;
    }
  }

  /// Build a 44-byte WAV header for PCM 16-bit mono audio.
  static Uint8List _wavHeader(int dataSize, int sampleRate) {
    final h = ByteData(44);
    // RIFF
    h.setUint8(0, 0x52); // R
    h.setUint8(1, 0x49); // I
    h.setUint8(2, 0x46); // F
    h.setUint8(3, 0x46); // F
    h.setUint32(4, 36 + dataSize, Endian.little);
    h.setUint8(8, 0x57); // W
    h.setUint8(9, 0x41); // A
    h.setUint8(10, 0x56); // V
    h.setUint8(11, 0x45); // E
    // fmt
    h.setUint8(12, 0x66); // f
    h.setUint8(13, 0x6D); // m
    h.setUint8(14, 0x74); // t
    h.setUint8(15, 0x20); // (space)
    h.setUint32(16, 16, Endian.little); // chunk size
    h.setUint16(20, 1, Endian.little); // PCM format
    h.setUint16(22, 1, Endian.little); // mono
    h.setUint32(24, sampleRate, Endian.little); // sample rate
    h.setUint32(28, sampleRate * 2, Endian.little); // byte rate
    h.setUint16(32, 2, Endian.little); // block align
    h.setUint16(34, 16, Endian.little); // bits per sample
    // data
    h.setUint8(36, 0x64); // d
    h.setUint8(37, 0x61); // a
    h.setUint8(38, 0x74); // t
    h.setUint8(39, 0x61); // a
    h.setUint32(40, dataSize, Endian.little);
    return h.buffer.asUint8List();
  }

  // ─── File Playback ───

  Future<void> _ensureFilePlayerOpen() async {
    if (!_filePlayerOpened) {
      await _savedFilePlayer.openPlayer();
      _filePlayerOpened = true;
      debugPrint('AudioService: File player opened');
    }
  }

  /// Play a saved WAV file. Calls [onFinished] when playback completes.
  Future<void> playFile(String path, {VoidCallback? onFinished}) async {
    await stopFilePlayback();
    await _ensureFilePlayerOpen();
    currentlyPlayingFile = path;
    await _savedFilePlayer.startPlayer(
      fromURI: path,
      codec: Codec.pcm16WAV,
      whenFinished: () {
        currentlyPlayingFile = null;
        debugPrint('AudioService: File playback finished');
        onFinished?.call();
      },
    );
    debugPrint('AudioService: Playing file $path');
  }

  Future<void> stopFilePlayback() async {
    if (currentlyPlayingFile == null) return;
    try {
      await _filePlayer?.stopPlayer();
    } catch (_) {}
    currentlyPlayingFile = null;
    debugPrint('AudioService: File playback stopped');
  }

  // ─── Lifecycle ───

  void dispose() {
    stopRecording();
    stopPlayback();
    stopFilePlayback();
    if (_playerOpened) _player?.closePlayer();
    if (_filePlayerOpened) _filePlayer?.closePlayer();
    _recorder?.dispose();
    _audioController.close();
  }
}

final audioServiceProvider = Provider<AudioService>((ref) {
  final service = AudioService();
  ref.onDispose(() => service.dispose());
  return service;
});
