"""WebSocket endpoint for Twilio Media Streams (outbound calls)."""

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.audio_bridge import AudioBridge

router = APIRouter(tags=["twilio"])


@router.websocket("/ws/twilio/{call_id}")
async def twilio_media_stream(websocket: WebSocket, call_id: str):
    """Handle Twilio Media Streams for outbound PSTN calls.

    Twilio sends mulaw 8kHz audio; we convert to PCM 16kHz for Gemini
    and convert Gemini's PCM 24kHz response back to mulaw 8kHz for Twilio.

    TODO: Implement full ADK LiveRequestQueue integration in Phase 2 Day 8-9.
    """
    await websocket.accept()
    stream_sid = None
    bridge = AudioBridge()

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            event_type = data.get("event")

            if event_type == "connected":
                pass

            elif event_type == "start":
                stream_sid = data["start"]["streamSid"]

            elif event_type == "media":
                payload = data["media"]["payload"]
                # Convert Twilio mulaw to Gemini PCM
                _pcm_audio = bridge.twilio_to_gemini(payload)

                # TODO: Forward to ADK LiveRequestQueue
                # TODO: Get agent response, convert back, send to Twilio

            elif event_type == "stop":
                break

    except WebSocketDisconnect:
        pass
