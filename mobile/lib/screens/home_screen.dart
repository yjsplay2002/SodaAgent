import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../app/theme.dart';
import '../services/auth_service.dart';
import '../services/document_export_service.dart';
import '../services/session_catalog_service.dart';
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
                onSaveResponse: (entry) =>
                    _saveResponse(entry, session.conversationId),
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
    final currentUser = ref.watch(authStateProvider).valueOrNull;
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
          Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Soda',
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w600,
                  color: Colors.white,
                  letterSpacing: 1,
                ),
              ),
              if (currentUser?.displayName?.trim().isNotEmpty ?? false)
                Text(
                  currentUser!.displayName!.trim(),
                  style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.45),
                    fontSize: 11,
                  ),
                ),
            ],
          ),
          const Spacer(),
          Row(
            mainAxisSize: MainAxisSize.min,
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
                onPressed: _showConversationSheet,
                icon: const Icon(Icons.history_rounded, color: Colors.white),
                tooltip: 'Sessions',
              ),
              IconButton(
                onPressed: _signOut,
                icon: const Icon(Icons.logout_rounded, color: Colors.white),
                tooltip: 'Sign out',
              ),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _signOut() async {
    try {
      ref.read(voiceSessionProvider.notifier).disconnect();
      await ref.read(authServiceProvider).signOut();
    } on AuthException catch (error) {
      if (!mounted) {
        return;
      }
      _showSnackBar(error.message);
    } catch (_) {
      if (!mounted) {
        return;
      }
      _showSnackBar('Failed to sign out.');
    }
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

  void _showSnackBar(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _saveResponse(
    TranscriptEntry entry,
    String? conversationId,
  ) async {
    try {
      final exported = await ref
          .read(documentExportServiceProvider)
          .exportResponseAsText(entry: entry, conversationId: conversationId);
      if (!mounted) return;
      _showSnackBar('Saved to ${exported.path} (copied to clipboard)');
    } on DocumentExportException catch (error) {
      if (!mounted) return;
      _showSnackBar(error.message);
    } catch (_) {
      if (!mounted) return;
      _showSnackBar('Failed to save response.');
    }
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
      _showSnackBar('Saved to ${exported.path} (copied to clipboard)');
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

  Future<void> _showConversationSheet() async {
    final notifier = ref.read(voiceSessionProvider.notifier);
    await notifier.refreshSessions(_defaultServerUrl);
    if (!mounted) return;

    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: const Color(0xFF11161D),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (context) {
        final latest = ref.watch(voiceSessionProvider);
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Text(
                      'Sessions',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const Spacer(),
                    TextButton.icon(
                      onPressed: () async {
                        Navigator.of(context).pop();
                        await notifier.selectConversation(null);
                      },
                      icon: const Icon(Icons.add_rounded),
                      label: const Text('New session'),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                if (latest.conversationsLoading)
                  const Expanded(
                    child: Center(child: CircularProgressIndicator()),
                  )
                else if (latest.conversations.isEmpty)
                  Expanded(
                    child: Center(
                      child: Text(
                        'No saved sessions yet',
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.45),
                        ),
                      ),
                    ),
                  )
                else
                  Expanded(
                    child: ListView.separated(
                      itemCount: latest.conversations.length,
                      separatorBuilder: (_, _) => Divider(
                        color: Colors.white.withValues(alpha: 0.08),
                        height: 1,
                      ),
                      itemBuilder: (context, index) {
                        final item = latest.conversations[index];
                        final selected =
                            item.conversationId == latest.conversationId;
                        return _ConversationTile(
                          summary: item,
                          selected: selected,
                          onTap: () async {
                            Navigator.of(context).pop();
                            await notifier.selectConversation(item);
                          },
                        );
                      },
                    ),
                  ),
                if (latest.conversationsError != null) ...[
                  const SizedBox(height: 8),
                  Text(
                    latest.conversationsError!,
                    style: TextStyle(color: Colors.red.shade300, fontSize: 12),
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }
}

class _ConversationTile extends StatelessWidget {
  final ConversationSummary summary;
  final bool selected;
  final VoidCallback onTap;

  const _ConversationTile({
    required this.summary,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      onTap: onTap,
      title: Text(
        summary.title,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: TextStyle(
          color: selected ? SodaTheme.accent : Colors.white,
          fontWeight: FontWeight.w600,
        ),
      ),
      subtitle: Padding(
        padding: const EdgeInsets.only(top: 6),
        child: Text(
          summary.preview.isEmpty
              ? '${summary.domain} session'
              : summary.preview,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(
            color: Colors.white.withValues(alpha: 0.58),
            height: 1.35,
          ),
        ),
      ),
      trailing: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Text(
            _formatUpdatedAt(summary.updatedAt),
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.42),
              fontSize: 11,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            '${summary.turnCount} turns',
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.32),
              fontSize: 11,
            ),
          ),
        ],
      ),
    );
  }

  static String _formatUpdatedAt(DateTime value) {
    final now = DateTime.now();
    final diff = now.difference(value);
    if (diff.inMinutes < 1) return 'now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m';
    if (diff.inHours < 24) return '${diff.inHours}h';
    return '${diff.inDays}d';
  }
}
