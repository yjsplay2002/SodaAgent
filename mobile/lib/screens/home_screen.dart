import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../app/theme.dart';
import '../services/document_export_service.dart';
import '../services/voice_session.dart';
import '../services/websocket_service.dart' show WsConnectionState;
import '../widgets/transcript_overlay.dart';
import '../widgets/voice_orb.dart';

const _defaultServerUrl = 'https://soda-agent-xn3v7zelza-uc.a.run.app';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  final _textController = TextEditingController();
  bool _isExporting = false;

  @override
  void initState() {
    super.initState();
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
              isUserSpeechDetected: session.isUserSpeechDetected,
              onTap: () => _toggleSession(session),
            ),
            const SizedBox(height: 12),
            _buildStateLabel(session),
            const SizedBox(height: 8),
            if (session.voiceState == VoiceState.listening)
              _buildListeningStatus(session),
            if (session.voiceState == VoiceState.listening)
              const SizedBox(height: 8),
            if (session.connectionState == WsConnectionState.connected)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 40),
                child: Text(
                  session.micAvailable
                      ? session.isUserSpeechDetected
                            ? 'Voice is being recognized'
                            : 'Speak toward the mic'
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
    final hasTranscripts = session.transcripts.any(
      (entry) => entry.text.trim().isNotEmpty,
    );
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
                  ? [
                      BoxShadow(
                        color: color.withValues(alpha: 0.5),
                        blurRadius: 6,
                      ),
                    ]
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
          SizedBox(
            width: 120,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                IconButton(
                  onPressed: hasTranscripts && !_isExporting
                      ? () => _exportConversation(session)
                      : null,
                  icon: _isExporting
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.download_rounded, color: Colors.white),
                  tooltip: 'Export conversation',
                ),
                IconButton(
                  onPressed: () => _openVoiceSettings(session),
                  icon: const Icon(Icons.tune_rounded, color: Colors.white),
                  tooltip: 'Voice settings',
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStateLabel(VoiceSessionState session) {
    final label = switch (session.voiceState) {
      VoiceState.idle =>
        session.connectionState == WsConnectionState.connected
            ? 'Tap mic to speak'
            : 'Tap to connect',
      VoiceState.listening =>
        session.isUserSpeechDetected
            ? 'Voice detected'
            : 'Listening for your voice...',
      VoiceState.thinking =>
        session.currentToolCall != null
            ? 'Using ${session.currentToolCall}...'
            : 'Thinking...',
      VoiceState.speaking =>
        session.isAssistantDucked
            ? 'Listening over assistant...'
            : 'Speaking...',
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

  Widget _buildListeningStatus(VoiceSessionState session) {
    final detected = session.isUserSpeechDetected;
    final color = detected ? SodaTheme.listening : Colors.white;

    return AnimatedContainer(
      duration: const Duration(milliseconds: 180),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: detected
            ? SodaTheme.listening.withValues(alpha: 0.14)
            : Colors.white.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(
          color: detected
              ? SodaTheme.listening.withValues(alpha: 0.45)
              : Colors.white.withValues(alpha: 0.12),
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            detected ? Icons.graphic_eq_rounded : Icons.hearing_rounded,
            size: 14,
            color: color.withValues(alpha: detected ? 0.95 : 0.7),
          ),
          const SizedBox(width: 6),
          Text(
            detected ? 'Recognizing speech' : 'Waiting for speech',
            style: TextStyle(
              color: color.withValues(alpha: detected ? 0.95 : 0.7),
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
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
                hintStyle: TextStyle(
                  color: Colors.white.withValues(alpha: 0.3),
                ),
                filled: true,
                fillColor: Colors.white.withValues(alpha: 0.08),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: BorderSide.none,
                ),
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 20,
                  vertical: 12,
                ),
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
      notifier.connect(_defaultServerUrl);
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

  Future<void> _openVoiceSettings(VoiceSessionState session) async {
    var draft = session.vadConfig;

    await showDialog<void>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              backgroundColor: const Color(0xFF151922),
              title: const Text(
                'Voice Settings',
                style: TextStyle(color: Colors.white),
              ),
              content: SizedBox(
                width: 420,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _VadSlider(
                      title: 'Voice detection sensitivity',
                      valueLabel:
                          '${draft.speechRmsThreshold.toStringAsFixed(0)} level',
                      helper:
                          'Higher values ignore more background noise, but may miss quiet speech.',
                      min: 100,
                      max: 2000,
                      divisions: 38,
                      value: draft.speechRmsThreshold.clamp(100, 2000),
                      onChanged: (value) {
                        setDialogState(() {
                          draft = draft.copyWith(speechRmsThreshold: value);
                        });
                      },
                    ),
                    const SizedBox(height: 12),
                    _VadSlider(
                      title: 'Pause before reply',
                      valueLabel: '${draft.endSilenceMs.toStringAsFixed(0)} ms',
                      helper:
                          'How long Soda waits after you stop speaking before it answers.',
                      min: 200,
                      max: 1800,
                      divisions: 32,
                      value: draft.endSilenceMs.clamp(200, 1800),
                      onChanged: (value) {
                        setDialogState(() {
                          draft = draft.copyWith(endSilenceMs: value);
                        });
                      },
                    ),
                    const SizedBox(height: 12),
                    _VadSlider(
                      title: 'Minimum speech length',
                      valueLabel: '${draft.minSpeechMs.toStringAsFixed(0)} ms',
                      helper:
                          'Very short bursts below this are treated as noise instead of a real request.',
                      min: 50,
                      max: 800,
                      divisions: 30,
                      value: draft.minSpeechMs.clamp(50, 800),
                      onChanged: (value) {
                        setDialogState(() {
                          draft = draft.copyWith(minSpeechMs: value);
                        });
                      },
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () {
                    setDialogState(() {
                      draft = VadConfig.defaults;
                    });
                  },
                  child: const Text('Reset'),
                ),
                TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: () {
                    ref
                        .read(voiceSessionProvider.notifier)
                        .updateVadConfig(draft);
                    Navigator.of(context).pop();
                    _showSnackBar('Voice settings updated.');
                  },
                  child: const Text('Apply'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  void _showSnackBar(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _exportConversation(VoiceSessionState session) async {
    setState(() {
      _isExporting = true;
    });

    try {
      final exported = await ref
          .read(documentExportServiceProvider)
          .exportConversationAsText(
            transcripts: session.transcripts,
            conversationId: session.conversationId,
          );
      if (!mounted) {
        return;
      }
      _showSnackBar('Saved ${exported.fileName} to ${exported.path}');
    } on DocumentExportException catch (error) {
      if (!mounted) {
        return;
      }
      _showSnackBar(error.message);
    } catch (_) {
      if (!mounted) {
        return;
      }
      _showSnackBar('Failed to export conversation.');
    } finally {
      if (mounted) {
        setState(() {
          _isExporting = false;
        });
      }
    }
  }
}

class _VadSlider extends StatelessWidget {
  final String title;
  final String valueLabel;
  final String helper;
  final double min;
  final double max;
  final int divisions;
  final double value;
  final ValueChanged<double> onChanged;

  const _VadSlider({
    required this.title,
    required this.valueLabel,
    required this.helper,
    required this.min,
    required this.max,
    required this.divisions,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                title,
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            Text(
              valueLabel,
              style: TextStyle(
                color: SodaTheme.accent,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
        const SizedBox(height: 4),
        Text(
          helper,
          style: TextStyle(
            color: Colors.white.withValues(alpha: 0.6),
            fontSize: 12,
            height: 1.35,
          ),
        ),
        Slider(
          min: min,
          max: max,
          divisions: divisions,
          value: value,
          activeColor: SodaTheme.accent,
          onChanged: onChanged,
        ),
      ],
    );
  }
}
