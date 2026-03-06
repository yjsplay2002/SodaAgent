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

# ---------------------------------------------------------------------------
# Tool registry for nudge re-execution
# (Native audio models often don't speak after tool results — known Gemini
#  limitation.  When that happens we re-execute the tool, inject the result
#  as a user text message, and the model speaks it.)
# ---------------------------------------------------------------------------
from soda_agent.tools.calendar_tools import get_upcoming_events, create_event, get_free_slots
from soda_agent.tools.maps_tools import get_directions, get_eta, search_places
from soda_agent.tools.weather_tools import get_current_weather, get_forecast
from soda_agent.tools.music_tools import play_song, pause_music, skip_track
from soda_agent.tools.messaging_tools import read_messages, send_message
from soda_agent.tools.vehicle_tools import get_vehicle_status

_TOOL_MAP = {
    "get_upcoming_events": get_upcoming_events,
    "create_event": create_event,
    "get_free_slots": get_free_slots,
    "get_directions": get_directions,
    "get_eta": get_eta,
    "search_places": search_places,
    "get_current_weather": get_current_weather,
    "get_forecast": get_forecast,
    "play_song": play_song,
    "pause_music": pause_music,
    "skip_track": skip_track,
    "read_messages": read_messages,
    "send_message": send_message,
    "get_vehicle_status": get_vehicle_status,
}


def _execute_tool(name: str, args: dict):
    """Re-execute a tool by name.  Returns the result dict or None."""
    func = _TOOL_MAP.get(name)
    if not func:
        return None
    try:
        return func(**args)
    except Exception as e:
        logger.error("Tool re-execution error (%s): %s", name, e)
        return None


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
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Aoede"  # female voice
                )
            )
        ),
    )

    async def forward_agent_events():
        """Read events from ADK agent and send to Flutter client.
        but produces no audio afterwards, we re-execute the tool and
        inject the result as a user text message so the model speaks it.
        Only nudges ONCE per user turn to prevent infinite tool-call loops.
        """
        # --- Nudge state tracking ---
        pending_tool_name: str | None = None
        pending_tool_args: dict = {}
        got_audio_after_tool = False
        turn_complete_count = 0
        already_nudged = False  # Prevents infinite nudge → tool_call → nudge loop

        try:
            async for event in runner.run_live(
                session=session,
                live_request_queue=live_queue,
                run_config=run_config,
            ):
                # --- DEBUG: log every event from ADK ---
                _log_event_debug(event)
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.function_call:
                            pending_tool_name = part.function_call.name
                            pending_tool_args = (
                                dict(part.function_call.args)
                                if part.function_call.args
                                else {}
                            )
                            got_audio_after_tool = False
                            turn_complete_count = 0
                            logger.info(
                                "NUDGE-TRACK: function_call detected: %s(%s) already_nudged=%s",
                                pending_tool_name,
                                pending_tool_args,
                                already_nudged,
                            )
                        elif (
                            part.inline_data
                            and part.inline_data.mime_type
                            and "audio" in part.inline_data.mime_type
                        ):
                            got_audio_after_tool = True
                # Reset nudge lock on new user input
                in_tx = getattr(event, 'input_transcription', None)
                if in_tx:
                    already_nudged = False
                # Forward event to client as usual
                try:
                    await _send_event_to_client(websocket, event)
                except WebSocketDisconnect:
                    break
                # --- Nudge: detect missing audio after tool call ---
                if (
                    event.is_final_response()
                    and pending_tool_name
                    and not already_nudged
                ):
                    turn_complete_count += 1
                    if turn_complete_count >= 2 and not got_audio_after_tool:
                        logger.info(
                            "NUDGE: No audio after tool %s "
                            "(turn_complete #%d). Sending result as text.",
                            pending_tool_name,
                            turn_complete_count,
                        )
                        result = _execute_tool(
                            pending_tool_name, pending_tool_args
                        )
                        if result:
                            summary = json.dumps(result, ensure_ascii=False)
                            live_queue.send(
                                LiveRequest(
                                    content=types.Content(
                                        role="user",
                                        parts=[
                                            types.Part(
                                                text=(
                                                    f"Here is the data: {summary}\n"
                                                    "Summarize this information for me briefly. "
                                                    "Do NOT call any tools."
                                                )
                                            )
                                        ],
                                    )
                                )
                            )
                        # Lock: only nudge once per user turn
                        already_nudged = True
                        pending_tool_name = None
                        pending_tool_args = {}
                        got_audio_after_tool = False
                        turn_complete_count = 0

        except Exception as e:
            logger.exception("Agent event error: %s", e)
            try:
                await websocket.send_json(
                    {"type": "error", "message": str(e)}
                )
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


def _log_event_debug(event) -> None:
    """Log detailed event info for debugging tool call responses."""
    parts_info = []
    if event.content and event.content.parts:
        for p in event.content.parts:
            if p.inline_data:
                parts_info.append(
                    f"inline_data({p.inline_data.mime_type}, "
                    f"{len(p.inline_data.data) if p.inline_data.data else 0}b)"
                )
            elif getattr(p, 'text', None):
                thought = getattr(p, 'thought', False)
                parts_info.append(
                    f"text(thought={thought}, len={len(p.text)}, "
                    f"preview={p.text[:80]!r})"
                )
            elif p.function_call:
                parts_info.append(f"function_call({p.function_call.name})")
            elif p.function_response:
                parts_info.append(f"function_response({p.function_response.name})")
            else:
                parts_info.append(f"unknown_part({type(p).__name__})")

    out_tx = getattr(event, 'output_transcription', None)
    in_tx = getattr(event, 'input_transcription', None)
    is_final = event.is_final_response()
    author = getattr(event, 'author', 'N/A')
    role = event.content.role if event.content else 'N/A'

    logger.info(
        "EVENT: author=%s role=%s is_final=%s out_tx=%s in_tx=%s parts=[%s]",
        author, role, is_final,
        bool(out_tx), bool(in_tx),
        ', '.join(parts_info) if parts_info else 'EMPTY',
    )


async def _send_event_to_client(websocket: WebSocket, event) -> None:
    """Convert ADK event to client-friendly JSON and send."""
    # 1. Output transcription: model의 음성 답변 텍스트 (AUDIO 모드의 실제 응답)
    #    event.content.parts 가 아닌 별도 필드로 제공됨 (ADK Live 특성)
    output_transcription = getattr(event, 'output_transcription', None)
    if output_transcription:
        parts = getattr(output_transcription, 'parts', None)
        if parts:
            for part in parts:
                if getattr(part, 'text', None):
                    await websocket.send_json(
                        {"type": "transcript", "role": "model", "text": part.text}
                    )
        elif isinstance(output_transcription, str) and output_transcription:
            await websocket.send_json(
                {"type": "transcript", "role": "model", "text": output_transcription}
            )

    # 2. Input transcription: 사용자 음성 텍스트
    input_transcription = getattr(event, 'input_transcription', None)
    if input_transcription:
        parts = getattr(input_transcription, 'parts', None)
        if parts:
            for part in parts:
                if getattr(part, 'text', None):
                    await websocket.send_json(
                        {"type": "transcript", "role": "user", "text": part.text}
                    )
        elif isinstance(input_transcription, str) and input_transcription:
            await websocket.send_json(
                {"type": "transcript", "role": "user", "text": input_transcription}
            )

    # 3. event.content.parts: 오디오 데이터, 함수 호출, (필터된) thinking 토큰
    #
    # IMPORTANT: Gemini native-audio models mark EVERY audio-chunk event
    # as is_final=True.  Transcription events (out_tx / in_tx) also arrive
    # with is_final=True BEFORE the last audio chunk.  We must only send
    # turn_complete for truly-empty final events with no transcription.
    has_transcription = bool(output_transcription) or bool(input_transcription)
    if not event.content or not event.content.parts:
        if event.is_final_response() and not has_transcription:
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
            sent_audio = True
        # Text: thought 필터 (thinking 토큰은 클라이언트로 보내지 않음)
        elif getattr(part, 'text', None):
            if getattr(part, 'thought', False) is True:
                logger.debug("Skipping thought: %s", part.text[:80])
                continue
            if not output_transcription:
                role = event.content.role or "model"
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

    # Only send turn_complete for truly final events that carry
    # neither audio data nor transcription updates.
    if event.is_final_response() and not sent_audio and not has_transcription:
        await websocket.send_json({"type": "turn_complete"})
