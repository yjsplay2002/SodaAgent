import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'audio_service.dart';
import 'websocket_service.dart';

enum VoiceState { idle, listening, thinking, speaking }

class VoiceSessionState {
  final VoiceState voiceState;
  final WsConnectionState connectionState;
  final List<TranscriptEntry> transcripts;
  final String? currentToolCall;
  final bool micAvailable;

  const VoiceSessionState({
    this.voiceState = VoiceState.idle,
    this.connectionState = WsConnectionState.disconnected,
    this.transcripts = const [],
    this.currentToolCall,
    this.micAvailable = false,
  });

  VoiceSessionState copyWith({
    VoiceState? voiceState,
    WsConnectionState? connectionState,
    List<TranscriptEntry>? transcripts,
    String? currentToolCall,
    bool? micAvailable,
  }) => VoiceSessionState(
    voiceState: voiceState ?? this.voiceState,
    connectionState: connectionState ?? this.connectionState,
    transcripts: transcripts ?? this.transcripts,
    currentToolCall: currentToolCall,
    micAvailable: micAvailable ?? this.micAvailable,
  );
}

class TranscriptEntry {
  final String role;
  final String text;
  final DateTime timestamp;

  TranscriptEntry({required this.role, required this.text, DateTime? timestamp})
    : timestamp = timestamp ?? DateTime.now();
}

class VoiceSessionNotifier extends StateNotifier<VoiceSessionState> {
  final WebSocketService _ws;
  final AudioService _audio;
  StreamSubscription? _msgSub;
  StreamSubscription? _stateSub;
  StreamSubscription? _micSub;


  VoiceSessionNotifier(this._ws, this._audio)
    : super(const VoiceSessionState()) {
    _stateSub = _ws.stateStream.listen((s) {
      state = state.copyWith(connectionState: s);
    });

    _msgSub = _ws.messages.listen(_handleMessage);
  }

  // ---------- connection ----------

  void connect(String serverUrl, String userId) {
    final wsUrl = serverUrl
        .replaceFirst('https://', 'wss://')
        .replaceFirst('http://', 'ws://');
    _ws.connect('$wsUrl/ws/mobile/$userId');
  }

  void _startMicStream() async {
    final started = await _audio.startRecording();
    if (started) {
      _micSub?.cancel();
      _micSub = _audio.audioStream.listen((chunk) {
        _ws.sendAudio(chunk);
      });
      state = state.copyWith(
        voiceState: VoiceState.listening,
        micAvailable: true,
      );
    } else {
      debugPrint('VoiceSession: Mic not available, text-only mode');
      state = state.copyWith(voiceState: VoiceState.idle, micAvailable: false);
    }
  }

  void toggleMic() async {
    if (state.connectionState != WsConnectionState.connected) return;
    if (state.micAvailable) {
      _micSub?.cancel();
      await _audio.stopRecording();
      state = state.copyWith(voiceState: VoiceState.idle, micAvailable: false);
      debugPrint('VoiceSession: Mic stopped');
    } else {
      _startMicStream();
    }
  }

  void sendText(String text) {
    _ws.sendText(text);
    final transcripts = [
      ...state.transcripts,
      TranscriptEntry(role: 'user', text: text),
    ];
    state = state.copyWith(
      transcripts: transcripts,
      voiceState: VoiceState.thinking,
    );
  }

  // ---------- message handler ----------

  void _handleMessage(WsMessage msg) {
    switch (msg.type) {
      case 'audio':
        if (msg.audioData != null) {
          _audio.startPlayback().then((_) {
            _audio.feedAudio(msg.audioData!);
          });
          state = state.copyWith(voiceState: VoiceState.speaking);
        }
      case 'transcript':
        if (msg.text == null || msg.text!.isEmpty) return;
        final transcripts = [
          ...state.transcripts,
          TranscriptEntry(role: msg.role ?? 'model', text: msg.text!.trim()),
        ];
        state = state.copyWith(
          transcripts: transcripts,
          voiceState: msg.role == 'user'
              ? VoiceState.thinking
              : VoiceState.speaking,
        );
      case 'tool_call':
        debugPrint('VoiceSession: Tool call=${msg.toolName}');
        state = state.copyWith(currentToolCall: msg.toolName);
      case 'interrupted':
        // Barge-in: user spoke while model was responding.
        // Flush buffered audio so the new response plays cleanly.
        debugPrint('VoiceSession: Barge-in — flushing audio buffer');
        _audio.stopPlayback();
        state = state.copyWith(
          voiceState: VoiceState.listening,
          currentToolCall: null,
        );

      case 'turn_complete':
        // Don't stop player — let buffered audio play through naturally.
        // Audio data arrives faster than real-time playback, so the
        // player buffer still has seconds of audio remaining.
        state = state.copyWith(
          voiceState: state.micAvailable
              ? VoiceState.listening
              : VoiceState.idle,
          currentToolCall: null,
        );

      case 'error':
        debugPrint('VoiceSession: Error=${msg.error}');

        _audio.stopPlayback();
        final errorTranscripts = [
          ...state.transcripts,
          TranscriptEntry(role: 'system', text: 'Error: ${msg.error}'),
        ];
        state = state.copyWith(
          transcripts: errorTranscripts,
          voiceState: state.micAvailable
              ? VoiceState.listening
              : VoiceState.idle,
        );

      default:
        debugPrint('VoiceSession: Unknown message type=${msg.type}');
    }
  }

  void disconnect() {

    _micSub?.cancel();
    _audio.stopRecording();
    _ws.disconnect();
    state = state.copyWith(
      voiceState: VoiceState.idle,
      connectionState: WsConnectionState.disconnected,
    );
  }

  @override
  void dispose() {

    _msgSub?.cancel();
    _stateSub?.cancel();
    _micSub?.cancel();
    disconnect();
    super.dispose();
  }
}

final voiceSessionProvider =
    StateNotifierProvider<VoiceSessionNotifier, VoiceSessionState>((ref) {
      final ws = ref.read(webSocketServiceProvider);
      final audio = ref.read(audioServiceProvider);
      return VoiceSessionNotifier(ws, audio);
    });
