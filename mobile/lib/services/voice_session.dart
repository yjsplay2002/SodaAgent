import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'audio_service.dart';
import 'location_service.dart';
import 'local_identity_service.dart';
import 'websocket_service.dart';

enum VoiceState { idle, listening, thinking, speaking }

const _noChange = Object();

class VadConfig {
  final double speechRmsThreshold;
  final double endSilenceMs;
  final double minSpeechMs;

  const VadConfig({
    required this.speechRmsThreshold,
    required this.endSilenceMs,
    required this.minSpeechMs,
  });

  static const defaults = VadConfig(
    speechRmsThreshold: 250,
    endSilenceMs: 650,
    minSpeechMs: 180,
  );

  VadConfig copyWith({
    double? speechRmsThreshold,
    double? endSilenceMs,
    double? minSpeechMs,
  }) => VadConfig(
    speechRmsThreshold: speechRmsThreshold ?? this.speechRmsThreshold,
    endSilenceMs: endSilenceMs ?? this.endSilenceMs,
    minSpeechMs: minSpeechMs ?? this.minSpeechMs,
  );

  Map<String, Object> toWsPayload() => {
    'speech_rms_threshold': speechRmsThreshold,
    'end_silence_ms': endSilenceMs,
    'min_speech_ms': minSpeechMs,
  };
}

class VoiceSessionState {
  final VoiceState voiceState;
  final WsConnectionState connectionState;
  final List<TranscriptEntry> transcripts;
  final String? currentToolCall;
  final bool micAvailable;
  final bool isUserSpeechDetected;
  final String? playingAudioPath;
  final String? conversationId;
  final String? activeUserTurnId;
  final String? activeAssistantTurnId;
  final bool isAssistantDucked;
  final VadConfig vadConfig;

  const VoiceSessionState({
    this.voiceState = VoiceState.idle,
    this.connectionState = WsConnectionState.disconnected,
    this.transcripts = const [],
    this.currentToolCall,
    this.micAvailable = false,
    this.isUserSpeechDetected = false,
    this.playingAudioPath,
    this.conversationId,
    this.activeUserTurnId,
    this.activeAssistantTurnId,
    this.isAssistantDucked = false,
    this.vadConfig = VadConfig.defaults,
  });

  VoiceSessionState copyWith({
    VoiceState? voiceState,
    WsConnectionState? connectionState,
    List<TranscriptEntry>? transcripts,
    Object? currentToolCall = _noChange,
    bool? micAvailable,
    bool? isUserSpeechDetected,
    Object? playingAudioPath = _noChange,
    Object? conversationId = _noChange,
    Object? activeUserTurnId = _noChange,
    Object? activeAssistantTurnId = _noChange,
    bool? isAssistantDucked,
    VadConfig? vadConfig,
  }) => VoiceSessionState(
    voiceState: voiceState ?? this.voiceState,
    connectionState: connectionState ?? this.connectionState,
    transcripts: transcripts ?? this.transcripts,
    currentToolCall: identical(currentToolCall, _noChange)
        ? this.currentToolCall
        : currentToolCall as String?,
    micAvailable: micAvailable ?? this.micAvailable,
    isUserSpeechDetected: isUserSpeechDetected ?? this.isUserSpeechDetected,
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
    vadConfig: vadConfig ?? this.vadConfig,
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
  static const int _minPersistedAssistantAudioBytes = 8192;

  final WebSocketService _ws;
  final Ref _ref;
  StreamSubscription? _msgSub;
  StreamSubscription? _stateSub;
  StreamSubscription? _micSub;
  bool _micToggleInFlight = false;

  final Map<String, List<Uint8List>> _audioBuffers = {};
  final Map<String, String> _pendingAudioPaths = {};
  final Map<String, int> _lastAudioSeqByTurn = {};
  final Set<String> _closedAssistantTurns = <String>{};

  VoiceSessionNotifier(this._ws, this._ref) : super(const VoiceSessionState()) {
    _stateSub = _ws.stateStream.listen((s) {
      state = state.copyWith(connectionState: s);
      if (s == WsConnectionState.connected) {
        _sendVadConfig(state.vadConfig);
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

  Future<void> _startMicStream() async {
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
        isUserSpeechDetected: false,
      );
      debugPrint('VoiceSession: Mic started');
    } else {
      debugPrint('VoiceSession: Mic not available, text-only mode');
      state = state.copyWith(
        voiceState: VoiceState.idle,
        micAvailable: false,
        isUserSpeechDetected: false,
      );
    }
  }

  void toggleMic() async {
    if (state.connectionState != WsConnectionState.connected) return;
    if (_micToggleInFlight) {
      debugPrint('VoiceSession: Ignoring mic toggle while busy');
      return;
    }

    _micToggleInFlight = true;
    try {
      if (state.micAvailable) {
        _micSub?.cancel();
        await _audio.stopRecording();
        _ws.sendEndTurn();
        state = state.copyWith(
          voiceState: VoiceState.idle,
          micAvailable: false,
          isUserSpeechDetected: false,
        );
        debugPrint('VoiceSession: Mic stopped');
      } else {
        await _startMicStream();
      }
    } finally {
      _micToggleInFlight = false;
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
    _sendVadConfig(state.vadConfig);
    _ws.sendText(text);
    state = state.copyWith(
      voiceState: VoiceState.thinking,
      currentToolCall: null,
      isUserSpeechDetected: false,
    );
  }

  void updateVadConfig(VadConfig config) {
    state = state.copyWith(vadConfig: config);
    _sendVadConfig(config);
  }

  void resetVadConfig() {
    updateVadConfig(VadConfig.defaults);
  }

  Future<void> _sendLocationContext() async {
    final context = await _location.buildLocationContextPayload();
    if (context == null) {
      return;
    }

    _ws.sendContextUpdate(context);
  }

  void _sendVadConfig(VadConfig config) {
    _ws.sendVadConfig(config.toWsPayload());
    debugPrint(
      'VoiceSession: Sent VAD config '
      'threshold=${config.speechRmsThreshold.toStringAsFixed(0)} '
      'silence=${config.endSilenceMs.toStringAsFixed(0)}ms '
      'minSpeech=${config.minSpeechMs.toStringAsFixed(0)}ms',
    );
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
    final normalized = _normalizeTranscriptText(text: text, role: role);

    final transcripts = [...state.transcripts];
    final index = transcripts.indexWhere((entry) => entry.turnId == turnId);
    if (index >= 0) {
      final pendingAudioPath = _pendingAudioPaths.remove(turnId);
      transcripts[index] = transcripts[index].copyWith(
        text: normalized ?? transcripts[index].text,
        audioPath: pendingAudioPath ?? transcripts[index].audioPath,
        isFinal: transcripts[index].isFinal || isFinal,
        isInterrupted: transcripts[index].isInterrupted || isInterrupted,
      );
    } else if (normalized != null) {
      transcripts.add(
        TranscriptEntry(
          turnId: turnId,
          role: role,
          text: normalized,
          audioPath: _pendingAudioPaths.remove(turnId),
          isFinal: isFinal,
          isInterrupted: isInterrupted,
        ),
      );
    } else {
      return;
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
    final totalBytes = chunks.fold<int>(0, (sum, chunk) => sum + chunk.length);
    if (totalBytes < _minPersistedAssistantAudioBytes) {
      debugPrint(
        'VoiceSession: Dropping short assistant audio '
        '(${totalBytes}b) for $turnId',
      );
      _pendingAudioPaths.remove(turnId);
      return;
    }

    _audio.saveWavFile(chunks).then((path) {
      if (path == null) return;

      final transcripts = [...state.transcripts];
      final index = transcripts.indexWhere((entry) => entry.turnId == turnId);
      if (index >= 0) {
        transcripts[index] = transcripts[index].copyWith(audioPath: path);
        _pendingAudioPaths.remove(turnId);
        state = state.copyWith(transcripts: transcripts);
      } else {
        transcripts.add(
          TranscriptEntry(
            turnId: turnId,
            role: 'assistant',
            text: 'Voice response',
            audioPath: path,
            isFinal: true,
          ),
        );
        _pendingAudioPaths.remove(turnId);
        state = state.copyWith(transcripts: transcripts);
      }
    });
  }

  void _discardAudioBufferForTurn(String turnId) {
    _audioBuffers.remove(turnId);
    _pendingAudioPaths.remove(turnId);
  }

  String? _normalizeTranscriptText({
    required String text,
    required String role,
  }) {
    final trimmed = text.trim();
    if (trimmed.isEmpty) {
      return null;
    }

    if (role != 'assistant' && role != 'model') {
      return trimmed;
    }

    final decoded = _tryDecodeJson(trimmed);
    if (decoded == null) {
      return trimmed;
    }

    return _summarizeStructuredTranscript(decoded);
  }

  Object? _tryDecodeJson(String text) {
    if (!(text.startsWith('{') && text.endsWith('}')) &&
        !(text.startsWith('[') && text.endsWith(']'))) {
      return null;
    }

    try {
      return jsonDecode(text);
    } catch (_) {
      return null;
    }
  }

  String? _summarizeStructuredTranscript(Object payload) {
    if (payload is! Map<String, dynamic>) {
      return null;
    }

    for (final key in const ['summary', 'message', 'result']) {
      final value = payload[key];
      if (value is String && value.trim().isNotEmpty) {
        return value.trim();
      }
    }

    final forecastSummary = _summarizeForecastPayload(payload);
    if (forecastSummary != null) {
      return forecastSummary;
    }

    return null;
  }

  String? _summarizeForecastPayload(Map<String, dynamic> payload) {
    if (payload['status'] != 'success') {
      return null;
    }

    final forecast = payload['forecast'];
    if (forecast is! List || forecast.isEmpty) {
      return null;
    }

    final city = (payload['city'] as String?)?.trim();
    final parts = <String>[];

    for (final item in forecast.take(3)) {
      if (item is! Map) {
        continue;
      }

      final day = item['day']?.toString().trim();
      final high = item['high']?.toString().trim();
      final low = item['low']?.toString().trim();
      final condition = item['condition']?.toString().trim();

      final segment = [
        if (day != null && day.isNotEmpty) day,
        if (condition != null && condition.isNotEmpty) condition,
        if (high != null && low != null && high.isNotEmpty && low.isNotEmpty)
          '$low to $high',
      ].join(', ');

      if (segment.isNotEmpty) {
        parts.add(segment);
      }
    }

    if (parts.isEmpty) {
      return null;
    }

    final location = city == null || city.isEmpty
        ? 'Forecast'
        : city == 'your current location'
        ? 'Forecast near you'
        : 'Forecast for $city';

    return '$location: ${parts.join(' · ')}';
  }

  void _handleMessage(WsMessage msg) {
    switch (msg.type) {
      case 'session_ready':
        state = state.copyWith(conversationId: msg.conversationId);
        _identity.saveConversationId(msg.conversationId);

      case 'turn_started':
        if (msg.role == 'assistant' && msg.turnId != null) {
          _closedAssistantTurns.remove(msg.turnId);
          _lastAudioSeqByTurn.remove(msg.turnId);
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
          isUserSpeechDetected: msg.role == 'user',
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
          isUserSpeechDetected: false,
          isAssistantDucked: false,
        );

      case 'audio':
        final turnId = msg.turnId;
        if (turnId == null || msg.audioData == null) return;
        debugPrint(
          'VoiceSession: Assistant audio turn=$turnId '
          'seq=${msg.seq} bytes=${msg.audioData!.length}',
        );
        if (_closedAssistantTurns.contains(turnId)) {
          debugPrint('VoiceSession: Dropping closed-turn audio for $turnId');
          return;
        }
        final seq = msg.seq;
        if (seq != null) {
          final lastSeq = _lastAudioSeqByTurn[turnId];
          if (lastSeq != null && seq <= lastSeq) {
            debugPrint(
              'VoiceSession: Dropping duplicate/stale audio '
              'for $turnId seq=$seq last=$lastSeq',
            );
            return;
          }
          _lastAudioSeqByTurn[turnId] = seq;
        }
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
          isUserSpeechDetected: false,
          isAssistantDucked: false,
        );

      case 'tool_call':
        debugPrint('VoiceSession: Tool call=${msg.toolName}');
        state = state.copyWith(
          currentToolCall: msg.toolName,
          activeAssistantTurnId: msg.turnId ?? state.activeAssistantTurnId,
          voiceState: VoiceState.thinking,
          isUserSpeechDetected: false,
        );

      case 'tool_finished':
        state = state.copyWith(
          currentToolCall: null,
          activeAssistantTurnId: msg.turnId ?? state.activeAssistantTurnId,
          voiceState: VoiceState.thinking,
          isUserSpeechDetected: false,
        );

      case 'assistant_cancelled':
        final turnId = msg.turnId;
        if (turnId == null) return;
        _closedAssistantTurns.add(turnId);
        debugPrint('VoiceSession: Assistant turn cancelled=$turnId');
        _markTranscriptCancelled(turnId, msg.text);
        _discardAudioBufferForTurn(turnId);
        _audio.stopPlayback();
        state = state.copyWith(
          activeAssistantTurnId: state.activeAssistantTurnId == turnId
              ? null
              : state.activeAssistantTurnId,
          voiceState: state.micAvailable
              ? VoiceState.listening
              : VoiceState.idle,
          currentToolCall: null,
          isUserSpeechDetected: false,
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
        debugPrint(
          'VoiceSession: Turn committed turn=$turnId role=${msg.role} '
          'status=${msg.status}',
        );
        if (msg.role == 'assistant') {
          _closedAssistantTurns.add(turnId);
          if (msg.status == null || msg.status == 'completed') {
            _saveAudioBufferForTurn(turnId);
          } else {
            _discardAudioBufferForTurn(turnId);
          }
          _audio.restorePlaybackVolume();
          state = state.copyWith(
            activeAssistantTurnId: state.activeAssistantTurnId == turnId
                ? null
                : state.activeAssistantTurnId,
            voiceState: state.micAvailable
                ? VoiceState.listening
                : VoiceState.idle,
            currentToolCall: null,
            isUserSpeechDetected: false,
            isAssistantDucked: false,
          );
        } else if (msg.role == 'user') {
          state = state.copyWith(
            activeUserTurnId: state.activeUserTurnId == turnId
                ? null
                : state.activeUserTurnId,
            voiceState: VoiceState.thinking,
            isUserSpeechDetected: false,
          );
        }

      case 'error':
        debugPrint('VoiceSession: Error=${msg.error}');
        _audioBuffers.clear();
        _pendingAudioPaths.clear();
        _lastAudioSeqByTurn.clear();
        _closedAssistantTurns.clear();
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
          isUserSpeechDetected: false,
          isAssistantDucked: false,
        );

      default:
        debugPrint('VoiceSession: Unknown message type=${msg.type}');
    }
  }

  void disconnect() {
    _audioBuffers.clear();
    _pendingAudioPaths.clear();
    _lastAudioSeqByTurn.clear();
    _closedAssistantTurns.clear();
    _micSub?.cancel();
    _audio.stopRecording();
    _audio.stopPlayback();
    _audio.restorePlaybackVolume();
    _audio.stopFilePlayback();
    _ws.disconnect();
    state = state.copyWith(
      voiceState: VoiceState.idle,
      connectionState: WsConnectionState.disconnected,
      isUserSpeechDetected: false,
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
