import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'audio_service.dart';
import 'location_service.dart';
import 'local_identity_service.dart';
import 'websocket_service.dart';

enum VoiceState { idle, listening, thinking, speaking }

const _noChange = Object();

class VoiceSessionState {
  final VoiceState voiceState;
  final WsConnectionState connectionState;
  final List<TranscriptEntry> transcripts;
  final String? currentToolCall;
  final bool micAvailable;
  final String? playingAudioPath;
  final String? conversationId;
  final String? activeUserTurnId;
  final String? activeAssistantTurnId;
  final bool isAssistantDucked;

  const VoiceSessionState({
    this.voiceState = VoiceState.idle,
    this.connectionState = WsConnectionState.disconnected,
    this.transcripts = const [],
    this.currentToolCall,
    this.micAvailable = false,
    this.playingAudioPath,
    this.conversationId,
    this.activeUserTurnId,
    this.activeAssistantTurnId,
    this.isAssistantDucked = false,
  });

  VoiceSessionState copyWith({
    VoiceState? voiceState,
    WsConnectionState? connectionState,
    List<TranscriptEntry>? transcripts,
    Object? currentToolCall = _noChange,
    bool? micAvailable,
    Object? playingAudioPath = _noChange,
    Object? conversationId = _noChange,
    Object? activeUserTurnId = _noChange,
    Object? activeAssistantTurnId = _noChange,
    bool? isAssistantDucked,
  }) => VoiceSessionState(
    voiceState: voiceState ?? this.voiceState,
    connectionState: connectionState ?? this.connectionState,
    transcripts: transcripts ?? this.transcripts,
    currentToolCall: identical(currentToolCall, _noChange)
        ? this.currentToolCall
        : currentToolCall as String?,
    micAvailable: micAvailable ?? this.micAvailable,
    playingAudioPath: identical(playingAudioPath, _noChange)
        ? this.playingAudioPath
        : playingAudioPath as String?,
    conversationId: identical(conversationId, _noChange)
        ? this.conversationId
        : conversationId as String?,
    activeUserTurnId: identical(activeUserTurnId, _noChange)
        ? this.activeUserTurnId
        : activeUserTurnId as String?,
    activeAssistantTurnId: identical(activeAssistantTurnId, _noChange)
        ? this.activeAssistantTurnId
        : activeAssistantTurnId as String?,
    isAssistantDucked: isAssistantDucked ?? this.isAssistantDucked,
  );
}

class TranscriptEntry {
  final String turnId;
  final String role;
  final String text;
  final DateTime timestamp;
  final String? audioPath;
  final bool isFinal;
  final bool isInterrupted;

  TranscriptEntry({
    required this.turnId,
    required this.role,
    required this.text,
    DateTime? timestamp,
    this.audioPath,
    this.isFinal = false,
    this.isInterrupted = false,
  }) : timestamp = timestamp ?? DateTime.now();

  TranscriptEntry copyWith({
    String? text,
    Object? audioPath = _noChange,
    bool? isFinal,
    bool? isInterrupted,
  }) => TranscriptEntry(
    turnId: turnId,
    role: role,
    text: text ?? this.text,
    timestamp: timestamp,
    audioPath: identical(audioPath, _noChange)
        ? this.audioPath
        : audioPath as String?,
    isFinal: isFinal ?? this.isFinal,
    isInterrupted: isInterrupted ?? this.isInterrupted,
  );
}

class VoiceSessionNotifier extends StateNotifier<VoiceSessionState> {
  final WebSocketService _ws;
  final Ref _ref;
  StreamSubscription? _msgSub;
  StreamSubscription? _stateSub;
  StreamSubscription? _micSub;

  final Map<String, List<Uint8List>> _audioBuffers = {};

  VoiceSessionNotifier(this._ws, this._ref) : super(const VoiceSessionState()) {
    _stateSub = _ws.stateStream.listen((s) {
      state = state.copyWith(connectionState: s);
      if (s == WsConnectionState.connected) {
        unawaited(_sendLocationContext());
      }
    });

    _msgSub = _ws.messages.listen(_handleMessage);
  }

  AudioService get _audio => _ref.read(audioServiceProvider);

  LocalIdentityService get _identity => _ref.read(localIdentityServiceProvider);
  LocationService get _location => _ref.read(locationServiceProvider);

  Future<void> connect(String serverUrl) async {
    final userId = await _identity.getOrCreateUserId();
    final conversationId =
        state.conversationId ?? await _identity.getConversationId();
    final wsUrl = serverUrl
        .replaceFirst('https://', 'wss://')
        .replaceFirst('http://', 'ws://');
    final uri = Uri.parse('$wsUrl/ws/mobile/$userId').replace(
      queryParameters: {
        if (conversationId != null && conversationId.isNotEmpty)
          'conversation_id': conversationId,
      },
    );
    _ws.connect(uri.toString());
    state = state.copyWith(conversationId: conversationId);
  }

  void _startMicStream() async {
    await _sendLocationContext();
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
    final trimmed = text.trim();
    if (trimmed.isEmpty) {
      return;
    }

    unawaited(_sendTextTurn(trimmed));
  }

  Future<void> _sendTextTurn(String text) async {
    await _sendLocationContext();
    _ws.sendText(text);
    state = state.copyWith(
      voiceState: VoiceState.thinking,
      currentToolCall: null,
    );
  }

  Future<void> _sendLocationContext() async {
    final context = await _location.buildLocationContextPrompt();
    if (context == null || context.isEmpty) {
      return;
    }

    _ws.sendContextUpdate(context);
  }

  void playAudio(String path) {
    _audio.stopFilePlayback();
    state = state.copyWith(playingAudioPath: path);
    _audio.playFile(
      path,
      onFinished: () {
        if (state.playingAudioPath == path) {
          state = state.copyWith(playingAudioPath: null);
        }
      },
    );
  }

  void stopAudio() {
    _audio.stopFilePlayback();
    state = state.copyWith(playingAudioPath: null);
  }

  void _upsertTranscript({
    required String turnId,
    required String role,
    required String text,
    bool isFinal = false,
    bool isInterrupted = false,
  }) {
    final trimmed = text.trim();
    if (trimmed.isEmpty) return;

    final transcripts = [...state.transcripts];
    final index = transcripts.indexWhere((entry) => entry.turnId == turnId);
    if (index >= 0) {
      transcripts[index] = transcripts[index].copyWith(
        text: trimmed,
        isFinal: transcripts[index].isFinal || isFinal,
        isInterrupted: transcripts[index].isInterrupted || isInterrupted,
      );
    } else {
      transcripts.add(
        TranscriptEntry(
          turnId: turnId,
          role: role,
          text: trimmed,
          isFinal: isFinal,
          isInterrupted: isInterrupted,
        ),
      );
    }

    state = state.copyWith(transcripts: transcripts);
  }

  void _markTranscriptCancelled(String turnId, String? text) {
    final transcripts = [...state.transcripts];
    final index = transcripts.indexWhere((entry) => entry.turnId == turnId);
    if (index >= 0) {
      transcripts[index] = transcripts[index].copyWith(
        text: (text != null && text.trim().isNotEmpty)
            ? text.trim()
            : transcripts[index].text,
        isFinal: true,
        isInterrupted: true,
      );
    } else {
      transcripts.add(
        TranscriptEntry(
          turnId: turnId,
          role: 'model',
          text: text?.trim().isNotEmpty == true ? text!.trim() : 'Interrupted',
          isFinal: true,
          isInterrupted: true,
        ),
      );
    }
    state = state.copyWith(transcripts: transcripts);
  }

  void _saveAudioBufferForTurn(String turnId) {
    final chunks = _audioBuffers.remove(turnId);
    if (chunks == null || chunks.isEmpty) return;

    _audio.saveWavFile(chunks).then((path) {
      if (path == null) return;

      final transcripts = [...state.transcripts];
      final index = transcripts.indexWhere((entry) => entry.turnId == turnId);
      if (index >= 0) {
        transcripts[index] = transcripts[index].copyWith(audioPath: path);
      } else {
        transcripts.add(
          TranscriptEntry(
            turnId: turnId,
            role: 'model',
            text: '\u{1F50A}',
            audioPath: path,
            isFinal: true,
          ),
        );
      }

      state = state.copyWith(transcripts: transcripts);
    });
  }

  void _handleMessage(WsMessage msg) {
    switch (msg.type) {
      case 'session_ready':
        state = state.copyWith(conversationId: msg.conversationId);
        _identity.saveConversationId(msg.conversationId);

      case 'turn_started':
        if (msg.role == 'assistant' && msg.turnId != null) {
          state = state.copyWith(
            activeAssistantTurnId: msg.turnId,
            voiceState: VoiceState.thinking,
            currentToolCall: null,
            isAssistantDucked: false,
          );
        } else if (msg.role == 'user' && msg.turnId != null) {
          state = state.copyWith(activeUserTurnId: msg.turnId);
        }

      case 'transcript_partial':
        if (msg.turnId == null || msg.text == null) return;
        _upsertTranscript(
          turnId: msg.turnId!,
          role: msg.role ?? 'model',
          text: msg.text!,
        );
        state = state.copyWith(
          activeUserTurnId: msg.role == 'user'
              ? msg.turnId
              : state.activeUserTurnId,
          activeAssistantTurnId: msg.role == 'assistant' || msg.role == 'model'
              ? msg.turnId
              : state.activeAssistantTurnId,
          voiceState: msg.role == 'user'
              ? VoiceState.listening
              : VoiceState.speaking,
          isAssistantDucked: false,
        );

      case 'transcript_final':
        if (msg.turnId == null || msg.text == null) return;
        _upsertTranscript(
          turnId: msg.turnId!,
          role: msg.role ?? 'model',
          text: msg.text!,
          isFinal: true,
        );
        state = state.copyWith(
          activeUserTurnId:
              msg.role == 'user' && state.activeUserTurnId == msg.turnId
              ? null
              : state.activeUserTurnId,
          activeAssistantTurnId:
              (msg.role == 'assistant' || msg.role == 'model') &&
                  state.activeAssistantTurnId == msg.turnId
              ? null
              : state.activeAssistantTurnId,
          voiceState: msg.role == 'user'
              ? VoiceState.thinking
              : VoiceState.speaking,
          isAssistantDucked: false,
        );

      case 'audio':
        final turnId = msg.turnId;
        if (turnId == null || msg.audioData == null) return;
        if (state.activeAssistantTurnId != null &&
            state.activeAssistantTurnId != turnId) {
          debugPrint('VoiceSession: Dropping stale audio for $turnId');
          return;
        }
        if (state.playingAudioPath != null) {
          _audio.stopFilePlayback();
          state = state.copyWith(playingAudioPath: null);
        }
        _audioBuffers.putIfAbsent(turnId, () => []).add(msg.audioData!);
        _audio.startPlayback().then((_) {
          _audio.feedAudio(msg.audioData!);
        });
        state = state.copyWith(
          activeAssistantTurnId: turnId,
          voiceState: VoiceState.speaking,
          isAssistantDucked: false,
        );

      case 'tool_call':
        debugPrint('VoiceSession: Tool call=${msg.toolName}');
        state = state.copyWith(
          currentToolCall: msg.toolName,
          activeAssistantTurnId: msg.turnId ?? state.activeAssistantTurnId,
          voiceState: VoiceState.thinking,
        );

      case 'tool_finished':
        state = state.copyWith(
          currentToolCall: null,
          activeAssistantTurnId: msg.turnId ?? state.activeAssistantTurnId,
          voiceState: VoiceState.thinking,
        );

      case 'assistant_cancelled':
        final turnId = msg.turnId;
        if (turnId == null) return;
        debugPrint('VoiceSession: Assistant turn cancelled=$turnId');
        _markTranscriptCancelled(turnId, msg.text);
        _saveAudioBufferForTurn(turnId);
        _audio.stopPlayback();
        state = state.copyWith(
          activeAssistantTurnId: state.activeAssistantTurnId == turnId
              ? null
              : state.activeAssistantTurnId,
          voiceState: state.micAvailable
              ? VoiceState.listening
              : VoiceState.idle,
          currentToolCall: null,
          isAssistantDucked: false,
        );

      case 'assistant_duck':
        _audio.duckPlayback();
        state = state.copyWith(isAssistantDucked: true);

      case 'assistant_resumed':
        _audio.restorePlaybackVolume();
        state = state.copyWith(isAssistantDucked: false);

      case 'turn_committed':
        final turnId = msg.turnId;
        if (turnId == null) return;
        if (msg.role == 'assistant') {
          _saveAudioBufferForTurn(turnId);
          _audio.restorePlaybackVolume();
          state = state.copyWith(
            activeAssistantTurnId: state.activeAssistantTurnId == turnId
                ? null
                : state.activeAssistantTurnId,
            voiceState: state.micAvailable
                ? VoiceState.listening
                : VoiceState.idle,
            currentToolCall: null,
            isAssistantDucked: false,
          );
        } else if (msg.role == 'user') {
          state = state.copyWith(
            activeUserTurnId: state.activeUserTurnId == turnId
                ? null
                : state.activeUserTurnId,
            voiceState: VoiceState.thinking,
          );
        }

      case 'error':
        debugPrint('VoiceSession: Error=${msg.error}');
        _audioBuffers.clear();
        _audio.stopPlayback();
        _audio.restorePlaybackVolume();
        final errorTranscripts = [
          ...state.transcripts,
          TranscriptEntry(
            turnId: 'system_${DateTime.now().millisecondsSinceEpoch}',
            role: 'system',
            text: 'Error: ${msg.error}',
            isFinal: true,
          ),
        ];
        state = state.copyWith(
          transcripts: errorTranscripts,
          voiceState: state.micAvailable
              ? VoiceState.listening
              : VoiceState.idle,
          isAssistantDucked: false,
        );

      default:
        debugPrint('VoiceSession: Unknown message type=${msg.type}');
    }
  }

  void disconnect() {
    _audioBuffers.clear();
    _micSub?.cancel();
    _audio.stopRecording();
    _audio.stopPlayback();
    _audio.restorePlaybackVolume();
    _audio.stopFilePlayback();
    _ws.disconnect();
    state = state.copyWith(
      voiceState: VoiceState.idle,
      connectionState: WsConnectionState.disconnected,
      playingAudioPath: null,
      activeUserTurnId: null,
      activeAssistantTurnId: null,
      currentToolCall: null,
      isAssistantDucked: false,
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
      return VoiceSessionNotifier(ws, ref);
    });

final localIdentityServiceProvider = Provider<LocalIdentityService>((ref) {
  return LocalIdentityService();
});
