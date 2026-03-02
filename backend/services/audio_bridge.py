"""Audio format conversion between Twilio mulaw 8kHz and Gemini PCM 16kHz."""

import audioop
import base64


class AudioBridge:
    """Converts audio between Twilio mulaw 8kHz and Gemini PCM 16kHz."""

    @staticmethod
    def twilio_to_gemini(payload_b64: str) -> bytes:
        """Convert Twilio mulaw 8kHz mono to PCM 16-bit 16kHz mono.

        Args:
            payload_b64: Base64-encoded mulaw audio from Twilio Media Streams.

        Returns:
            Raw PCM 16-bit 16kHz mono bytes for Gemini Live API.
        """
        raw_mulaw = base64.b64decode(payload_b64)
        pcm_8k = audioop.ulaw2lin(raw_mulaw, 2)
        pcm_16k, _ = audioop.ratecv(pcm_8k, 2, 1, 8000, 16000, None)
        return pcm_16k

    @staticmethod
    def gemini_to_twilio(pcm_24k: bytes) -> str:
        """Convert Gemini PCM 16-bit 24kHz mono to Twilio mulaw 8kHz base64.

        Args:
            pcm_24k: Raw PCM 16-bit 24kHz mono bytes from Gemini Live API.

        Returns:
            Base64-encoded mulaw audio string for Twilio Media Streams.
        """
        pcm_8k, _ = audioop.ratecv(pcm_24k, 2, 1, 24000, 8000, None)
        mulaw_8k = audioop.lin2ulaw(pcm_8k, 2)
        return base64.b64encode(mulaw_8k).decode("ascii")
