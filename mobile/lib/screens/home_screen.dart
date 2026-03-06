import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../app/theme.dart';
import '../services/voice_session.dart';
import '../services/websocket_service.dart' show WsConnectionState;
import '../widgets/transcript_overlay.dart';
import '../widgets/voice_orb.dart';

const _defaultServerUrl =
    'https://soda-agent-526653124749.us-central1.run.app';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  final _textController = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(voiceSessionProvider.notifier).connect(
            _defaultServerUrl,
            'user_${DateTime.now().millisecondsSinceEpoch}',
          );
    });
  }

  @override
  void dispose() {
    _textController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final session = ref.watch(voiceSessionProvider);

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(session),
            const Spacer(flex: 1),
            VoiceOrb(
              voiceState: session.voiceState,
              onTap: () => _toggleSession(session),
            ),
            const SizedBox(height: 12),
            _buildStateLabel(session),
            const SizedBox(height: 8),
            if (session.connectionState == WsConnectionState.connected)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 40),
                child: Text(
                  session.micAvailable
                      ? 'Tap orb to stop mic'
                      : 'Tap orb for voice, or type below',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.4),
                    fontSize: 12,
                  ),
                ),
              ),
            const Spacer(flex: 1),
            Expanded(
              flex: 5,
              child: TranscriptOverlay(
                transcripts: session.transcripts,
                voiceState: session.voiceState,
                playingAudioPath: session.playingAudioPath,
                onPlayAudio: (path) =>
                    ref.read(voiceSessionProvider.notifier).playAudio(path),
                onStopAudio: () =>
                    ref.read(voiceSessionProvider.notifier).stopAudio(),
              ),
            ),
            _buildTextInput(session),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader(VoiceSessionState session) {
    final connected = session.connectionState == WsConnectionState.connected;
    final color = switch (session.connectionState) {
      WsConnectionState.connected => SodaTheme.listening,
      WsConnectionState.connecting => Colors.amber,
      _ => SodaTheme.error,
    };
    final label = switch (session.connectionState) {
      WsConnectionState.connected => 'Connected',
      WsConnectionState.connecting => 'Connecting...',
      WsConnectionState.error => 'Connection error',
      WsConnectionState.disconnected => 'Disconnected',
    };

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
      child: Row(
        children: [
          Container(
            width: 10,
            height: 10,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: color,
              boxShadow: connected
                  ? [BoxShadow(color: color.withValues(alpha: 0.5), blurRadius: 6)]
                  : null,
            ),
          ),
          const SizedBox(width: 8),
          Text(label, style: Theme.of(context).textTheme.bodyMedium),
          const Spacer(),
          const Text(
            'Soda',
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.w600,
              color: Colors.white,
              letterSpacing: 1,
            ),
          ),
          const Spacer(),
          const SizedBox(width: 80),
        ],
      ),
    );
  }

  Widget _buildStateLabel(VoiceSessionState session) {
    final label = switch (session.voiceState) {
      VoiceState.idle => session.connectionState == WsConnectionState.connected
          ? 'Tap mic to speak'
          : 'Tap to connect',
      VoiceState.listening => 'Listening...',
      VoiceState.thinking => session.currentToolCall != null
          ? 'Using ${session.currentToolCall}...'
          : 'Thinking...',
      VoiceState.speaking => 'Speaking...',
    };

    return Text(
      label,
      style: TextStyle(
        color: Colors.white.withValues(alpha: 0.6),
        fontSize: 16,
        fontWeight: FontWeight.w400,
      ),
    );
  }

  Widget _buildTextInput(VoiceSessionState session) {
    final canSend = session.connectionState == WsConnectionState.connected;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _textController,
              enabled: canSend,
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                hintText: canSend ? 'Type a message...' : 'Connecting...',
                hintStyle:
                    TextStyle(color: Colors.white.withValues(alpha: 0.3)),
                filled: true,
                fillColor: Colors.white.withValues(alpha: 0.08),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: BorderSide.none,
                ),
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
              ),
              onSubmitted: canSend ? _sendText : null,
            ),
          ),
          const SizedBox(width: 8),
          IconButton(
            icon: Icon(
              Icons.send_rounded,
              color: canSend
                  ? SodaTheme.accent
                  : Colors.white.withValues(alpha: 0.2),
            ),
            onPressed: canSend ? () => _sendText(_textController.text) : null,
          ),
        ],
      ),
    );
  }

  void _toggleSession(VoiceSessionState session) {
    final notifier = ref.read(voiceSessionProvider.notifier);
    if (session.connectionState == WsConnectionState.disconnected ||
        session.connectionState == WsConnectionState.error) {
      notifier.connect(
        _defaultServerUrl,
        'user_${DateTime.now().millisecondsSinceEpoch}',
      );
    } else if (session.connectionState == WsConnectionState.connected) {
      // Toggle mic on/off
      notifier.toggleMic();
    }
  }

  void _sendText(String text) {
    if (text.trim().isEmpty) return;
    ref.read(voiceSessionProvider.notifier).sendText(text.trim());
    _textController.clear();
    FocusScope.of(context).unfocus();
  }
}
