import 'dart:math';

import 'package:flutter/material.dart';

import '../app/theme.dart';
import '../services/voice_session.dart';

class VoiceOrb extends StatefulWidget {
  final VoiceState voiceState;
  final bool isUserSpeechDetected;
  final VoidCallback? onTap;

  const VoiceOrb({
    super.key,
    required this.voiceState,
    required this.isUserSpeechDetected,
    this.onTap,
  });

  @override
  State<VoiceOrb> createState() => _VoiceOrbState();
}

class _VoiceOrbState extends State<VoiceOrb> with TickerProviderStateMixin {
  late AnimationController _pulseController;
  late AnimationController _waveController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);
    _waveController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2000),
    )..repeat();
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _waveController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final color = _colorForState(widget.voiceState);
    final isActive = widget.voiceState != VoiceState.idle;
    final showSpeechWave =
        widget.voiceState == VoiceState.speaking ||
        (widget.voiceState == VoiceState.listening &&
            widget.isUserSpeechDetected);

    return GestureDetector(
      onTap: widget.onTap,
      child: SizedBox(
        width: 200,
        height: 200,
        child: AnimatedBuilder(
          animation: Listenable.merge([_pulseController, _waveController]),
          builder: (context, child) {
            return CustomPaint(
              painter: _OrbPainter(
                color: color,
                pulseValue: isActive ? _pulseController.value : 0.0,
                waveValue: isActive ? _waveController.value : 0.0,
                voiceState: widget.voiceState,
                isUserSpeechDetected: widget.isUserSpeechDetected,
                showSpeechWave: showSpeechWave,
              ),
              child: Center(
                child: Icon(
                  _iconForState(
                    widget.voiceState,
                    isUserSpeechDetected: widget.isUserSpeechDetected,
                  ),
                  color: Colors.white,
                  size: 48,
                ),
              ),
            );
          },
        ),
      ),
    );
  }

  Color _colorForState(VoiceState state) => switch (state) {
    VoiceState.idle => Colors.grey.shade600,
    VoiceState.listening =>
      widget.isUserSpeechDetected
          ? SodaTheme.listening
          : SodaTheme.listening.withValues(alpha: 0.5),
    VoiceState.thinking => SodaTheme.accent,
    VoiceState.speaking => SodaTheme.accentGlow,
  };

  IconData _iconForState(
    VoiceState state, {
    required bool isUserSpeechDetected,
  }) => switch (state) {
    VoiceState.idle => Icons.mic_off,
    VoiceState.listening =>
      isUserSpeechDetected ? Icons.graphic_eq_rounded : Icons.mic_none_rounded,
    VoiceState.thinking => Icons.auto_awesome,
    VoiceState.speaking => Icons.volume_up,
  };
}

class _OrbPainter extends CustomPainter {
  final Color color;
  final double pulseValue;
  final double waveValue;
  final VoiceState voiceState;
  final bool isUserSpeechDetected;
  final bool showSpeechWave;

  _OrbPainter({
    required this.color,
    required this.pulseValue,
    required this.waveValue,
    required this.voiceState,
    required this.isUserSpeechDetected,
    required this.showSpeechWave,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final baseRadius = size.width * 0.28;

    // Outer glow rings
    for (var i = 3; i >= 1; i--) {
      final glowRadius =
          baseRadius +
          (i * 12) +
          (pulseValue * (isUserSpeechDetected ? 12 : 6));
      final opacity = ((isUserSpeechDetected ? 0.12 : 0.07) - i * 0.02).clamp(
        0.0,
        1.0,
      );
      canvas.drawCircle(
        center,
        glowRadius,
        Paint()
          ..color = color.withValues(alpha: opacity)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 12),
      );
    }

    if (showSpeechWave) {
      final wavePaint = Paint()
        ..color = color.withValues(alpha: 0.15)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2;

      for (var ring = 0; ring < 3; ring++) {
        final path = Path();
        final ringRadius = baseRadius + 20 + ring * 15;
        for (var angle = 0.0; angle < 2 * pi; angle += 0.05) {
          final wave =
              sin(angle * 6 + waveValue * 2 * pi + ring) * 4 * pulseValue;
          final r = ringRadius + wave;
          final x = center.dx + r * cos(angle);
          final y = center.dy + r * sin(angle);
          if (angle == 0) {
            path.moveTo(x, y);
          } else {
            path.lineTo(x, y);
          }
        }
        path.close();
        canvas.drawPath(path, wavePaint);
      }
    }

    // Main orb
    final gradient = RadialGradient(
      colors: [
        color.withValues(alpha: isUserSpeechDetected ? 0.95 : 0.72),
        color.withValues(alpha: 0.6),
        color.withValues(alpha: 0.3),
      ],
    );
    final orbRadius =
        baseRadius + (pulseValue * (isUserSpeechDetected ? 6 : 3));
    canvas.drawCircle(
      center,
      orbRadius,
      Paint()
        ..shader = gradient.createShader(
          Rect.fromCircle(center: center, radius: orbRadius),
        ),
    );

    // Inner bright core
    canvas.drawCircle(
      center,
      orbRadius * 0.5,
      Paint()
        ..color = Colors.white.withValues(
          alpha: (isUserSpeechDetected ? 0.22 : 0.14) + pulseValue * 0.1,
        ),
    );
  }

  @override
  bool shouldRepaint(covariant _OrbPainter old) => true;
}
