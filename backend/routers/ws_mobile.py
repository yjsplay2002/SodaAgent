"""WebSocket endpoint for Flutter mobile app bidirectional audio streaming.

Uses ADK Runner.run_live() with LiveRequestQueue to bridge
Flutter app audio <-> Gemini Live API (bidiGenerateContent).

Uses live_agent (flat, no sub-agents) to avoid transfer_to_agent issues
with bidiGenerateContent.
"""

import asyncio
import base64
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig
from google.adk.agents.live_request_queue import LiveRequestQueue, LiveRequest
from google.genai import types

from services.session_manager import session_service
from soda_agent.agent import live_agent

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mobile"])

APP_NAME = "soda_live_agent"

# Runner uses the flat live_agent (no sub-agents, all tools direct)
runner = Runner(
    agent=live_agent,
    app_name=APP_NAME,
    session_service=session_service,
)


@router.websocket("/ws/mobile/{user_id}")
async def mobile_voice_stream(websocket: WebSocket, user_id: str):
    """Bidirectional audio streaming between Flutter app and Gemini Live API.

    Protocol (client -> server):
        - JSON: {"type": "audio", "data": "<base64 PCM 16-bit 16kHz mono>"}
        - JSON: {"type": "text", "text": "hello"}
        - JSON: {"type": "end_turn"}

    Protocol (server -> client):
        - JSON: {"type": "audio", "data": "<base64 audio>"}
        - JSON: {"type": "transcript", "role": "model", "text": "..."}
        - JSON: {"type": "transcript", "role": "user", "text": "..."}
        - JSON: {"type": "tool_call", "name": "...", "args": {...}}
        - JSON: {"type": "turn_complete"}
        - JSON: {"type": "error", "message": "..."}
    """
    await websocket.accept()
    logger.info("Mobile client connected: user=%s", user_id)

    session = await session_service.create_session(
        app_name=APP_NAME, user_id=user_id
    )
    session_id = session.id
    logger.info("Session created: %s", session_id)

    live_queue = LiveRequestQueue()

    run_config = RunConfig(
        response_modalities=["AUDIO"],
        output_audio_transcription=types.AudioTranscriptionConfig(),
        input_audio_transcription=types.AudioTranscriptionConfig(),
    )

    async def forward_agent_events():
        """Read events from ADK agent and send to Flutter client."""
        try:
            async for event in runner.run_live(
                session=session,
                live_request_queue=live_queue,
                run_config=run_config,
            ):
                try:
                    await _send_event_to_client(websocket, event)
                except WebSocketDisconnect:
                    break
        except Exception as e:
            logger.exception("Agent event error: %s", e)
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
            except Exception:
                pass

    async def process_client_messages():
        """Read messages from Flutter client and feed to ADK LiveRequestQueue."""
        try:
            while True:
                raw = await websocket.receive_text()
                msg = json.loads(raw)
                msg_type = msg.get("type", "")

                if msg_type == "audio":
                    audio_bytes = base64.b64decode(msg["data"])
                    live_queue.send(
                        LiveRequest(
                            blob=types.Blob(
                                data=audio_bytes,
                                mime_type="audio/pcm;rate=16000",
                            )
                        )
                    )

                elif msg_type == "text":
                    live_queue.send(
                        LiveRequest(
                            content=types.Content(
                                role="user",
                                parts=[types.Part(text=msg["text"])],
                            )
                        )
                    )

                elif msg_type == "end_turn":
                    live_queue.send(LiveRequest(end_of_turn=True))

        except WebSocketDisconnect:
            logger.info("Client disconnected: user=%s", user_id)
        except Exception as e:
            logger.exception("Client message error: %s", e)

    try:
        tasks = [
            asyncio.create_task(forward_agent_events()),
            asyncio.create_task(process_client_messages()),
        ]
        done, pending = await asyncio.wait(
            tasks, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        for task in done:
            if task.exception():
                logger.error("Task error: %s", task.exception())
    finally:
        live_queue.close()
        logger.info("Session ended: user=%s session=%s", user_id, session_id)


async def _send_event_to_client(websocket: WebSocket, event) -> None:
    """Convert ADK event to client-friendly JSON and send."""
    if not event.content or not event.content.parts:
        if event.is_final_response():
            await websocket.send_json({"type": "turn_complete"})
        return

    for part in event.content.parts:
        # Audio response
        if part.inline_data and part.inline_data.mime_type and "audio" in part.inline_data.mime_type:
            await websocket.send_json(
                {
                    "type": "audio",
                    "data": base64.b64encode(part.inline_data.data).decode(),
                    "mime_type": part.inline_data.mime_type,
                }
            )

        # Text response (model transcript)
        elif part.text:
            role = event.content.role or "model"
            is_thought = getattr(part, 'thought', False)
            if is_thought:
                logger.debug("Skipping thought: %s", part.text[:60])
                continue
            await websocket.send_json(
                {"type": "transcript", "role": role, "text": part.text}
            )

        # Function call
        elif part.function_call:
            await websocket.send_json(
                {
                    "type": "tool_call",
                    "name": part.function_call.name,
                    "args": dict(part.function_call.args) if part.function_call.args else {},
                }
            )

    if event.is_final_response():
        await websocket.send_json({"type": "turn_complete"})
