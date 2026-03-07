import 'package:flutter/material.dart';

import '../services/voice_session.dart';

class TranscriptOverlay extends StatefulWidget {
  final List<TranscriptEntry> transcripts;
  final VoiceState voiceState;
  final String? playingAudioPath;
  final void Function(String path)? onPlayAudio;
  final VoidCallback? onStopAudio;

  const TranscriptOverlay({
    super.key,
    required this.transcripts,
    required this.voiceState,
    this.playingAudioPath,
    this.onPlayAudio,
    this.onStopAudio,
  });

  @override
  State<TranscriptOverlay> createState() => _TranscriptOverlayState();
}

class _TranscriptOverlayState extends State<TranscriptOverlay> {
  final _scrollController = ScrollController();

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  void didUpdateWidget(TranscriptOverlay oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.transcripts != oldWidget.transcripts ||
        widget.voiceState != oldWidget.voiceState) {
      _scrollToBottom();
    }
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final showTyping =
        widget.voiceState == VoiceState.thinking ||
        widget.voiceState == VoiceState.speaking;
    final itemCount = widget.transcripts.length + (showTyping ? 1 : 0);

    if (widget.transcripts.isEmpty && !showTyping) {
      return Center(
        child: Text(
          'Send a message to start',
          style: TextStyle(
            color: Colors.white.withValues(alpha: 0.3),
            fontSize: 14,
          ),
        ),
      );
    }

    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(vertical: 8),
      itemCount: itemCount,
      itemBuilder: (context, index) {
        if (index < widget.transcripts.length) {
          final entry = widget.transcripts[index];
          return _TranscriptBubble(
            entry: entry,
            isPlayingAudio:
                entry.audioPath != null &&
                entry.audioPath == widget.playingAudioPath,
            onPlayAudio: entry.audioPath != null
                ? () => widget.onPlayAudio?.call(entry.audioPath!)
                : null,
            onStopAudio: widget.onStopAudio,
          );
        }
        // Typing indicator as last item
        return const _TypingIndicator();
      },
    );
  }
}

class _TranscriptBubble extends StatelessWidget {
  final TranscriptEntry entry;
  final bool isPlayingAudio;
  final VoidCallback? onPlayAudio;
  final VoidCallback? onStopAudio;

  const _TranscriptBubble({
    required this.entry,
    this.isPlayingAudio = false,
    this.onPlayAudio,
    this.onStopAudio,
  });

  @override
  Widget build(BuildContext context) {
    final isUser = entry.role == 'user';
    final isSystem = entry.role == 'system';
    final hasAudio = entry.audioPath != null;
    final isInterrupted = entry.isInterrupted;
    final isLive = !entry.isFinal;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4, horizontal: 16),
      child: Align(
        alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
        child: Container(
          constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.75,
          ),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: isSystem
                ? Colors.red.withValues(alpha: 0.15)
                : isUser
                ? Colors.white.withValues(alpha: 0.1)
                : Colors.blue.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                entry.text,
                style: TextStyle(
                  color: isSystem
                      ? Colors.red.shade300
                      : isInterrupted
                      ? Colors.orange.shade200
                      : Colors.white.withValues(alpha: 0.9),
                  fontSize: 14,
                  height: 1.4,
                ),
              ),
              if (isInterrupted || isLive) ...[
                const SizedBox(height: 6),
                Text(
                  isInterrupted
                      ? 'Interrupted'
                      : isUser
                      ? 'Listening...'
                      : 'Speaking...',
                  style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.45),
                    fontSize: 11,
                    fontStyle: FontStyle.italic,
                  ),
                ),
              ],
              if (hasAudio && !isUser && !isSystem) ...[
                const SizedBox(height: 6),
                _AudioPlayRow(
                  isPlaying: isPlayingAudio,
                  onTap: isPlayingAudio ? onStopAudio : onPlayAudio,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _AudioPlayRow extends StatelessWidget {
  final bool isPlaying;
  final VoidCallback? onTap;

  const _AudioPlayRow({required this.isPlaying, this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            isPlaying ? Icons.stop_circle_outlined : Icons.play_circle_outlined,
            color: Colors.white.withValues(alpha: 0.6),
            size: 20,
          ),
          const SizedBox(width: 4),
          Text(
            isPlaying ? 'Stop' : 'Play',
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.5),
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }
}

class _TypingIndicator extends StatefulWidget {
  const _TypingIndicator();

  @override
  State<_TypingIndicator> createState() => _TypingIndicatorState();
}

class _TypingIndicatorState extends State<_TypingIndicator>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4, horizontal: 16),
      child: Align(
        alignment: Alignment.centerLeft,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            color: Colors.blue.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(16),
          ),
          child: AnimatedBuilder(
            animation: _controller,
            builder: (context, _) {
              return Row(
                mainAxisSize: MainAxisSize.min,
                children: List.generate(3, (i) {
                  final delay = i * 0.2;
                  final t = (_controller.value - delay) % 1.0;
                  final opacity = (t < 0.5)
                      ? 0.3 + 0.7 * (t * 2)
                      : 0.3 + 0.7 * (1 - (t - 0.5) * 2);
                  return Padding(
                    padding: EdgeInsets.only(right: i < 2 ? 4 : 0),
                    child: Opacity(
                      opacity: opacity.clamp(0.3, 1.0),
                      child: Container(
                        width: 8,
                        height: 8,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: Colors.white.withValues(alpha: 0.7),
                        ),
                      ),
                    ),
                  );
                }),
              );
            },
          ),
        ),
      ),
    );
  }
}
