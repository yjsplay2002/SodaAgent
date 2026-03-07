"""WebSocket endpoint for Flutter mobile app bidirectional audio streaming."""

from __future__ import annotations

import asyncio
import base64
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from google.adk.agents.live_request_queue import LiveRequest, LiveRequestQueue
from google.adk.agents.run_config import RunConfig
from google.adk.runners import Runner
from google.genai import types

from services.session_manager import session_service
from services.turn_controller import TurnController
from soda_agent.agent import live_agent
from soda_agent.tools.calendar_tools import (
    create_event,
    get_free_slots,
    get_upcoming_events,
)
from soda_agent.tools.maps_tools import (
    get_directions,
    get_eta,
    get_eta_from_query,
    search_places,
)
from soda_agent.tools.messaging_tools import read_messages, send_message
from soda_agent.tools.music_tools import pause_music, play_song, skip_track
from soda_agent.tools.vehicle_tools import get_vehicle_status
from soda_agent.tools.weather_tools import get_current_weather, get_forecast

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mobile"])

APP_NAME = "soda_live_agent"

runner = Runner(
    agent=live_agent,
    app_name=APP_NAME,
    session_service=session_service,
)

_TOOL_MAP = {
    "get_upcoming_events": get_upcoming_events,
    "create_event": create_event,
    "get_free_slots": get_free_slots,
    "get_directions": get_directions,
    "get_eta": get_eta,
    "get_eta_from_query": get_eta_from_query,
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
    """Re-execute a tool by name. Returns the result dict or None."""
    func = _TOOL_MAP.get(name)
    if not func:
        return None
    try:
        return func(**args)
    except Exception as exc:
        logger.error("Tool re-execution error (%s): %s", name, exc)
        return None


def _extract_transcription_texts(transcription) -> list[str]:
    if not transcription:
        return []

    parts = getattr(transcription, "parts", None)
    if parts:
        texts = []
        for part in parts:
            text = getattr(part, "text", None)
            if text and text.strip():
                texts.append(text.strip())
        return texts

    if isinstance(transcription, str) and transcription.strip():
        return [transcription.strip()]

    return []


def _tool_result_summary(name: str, result) -> str:
    if isinstance(result, dict):
        if name in {"get_eta", "get_eta_from_query"}:
            summary = _summarize_eta_result(result)
            if summary:
                return summary

        if name == "get_directions":
            summary = _summarize_directions_result(result)
            if summary:
                return summary

        message = result.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

        for key in ("summary", "result"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        compact = json.dumps(result, ensure_ascii=False)
        return compact[:280]

    if isinstance(result, str):
        return result[:280]

    return f"{name} completed."


def _contains_hangul(*values: object) -> bool:
    text = " ".join(str(value) for value in values if value)
    return bool(text and any("\uac00" <= ch <= "\ud7a3" for ch in text))


def _summarize_eta_result(result: dict) -> str | None:
    if result.get("status") != "success":
        return None

    origin = result.get("origin") or result.get("resolved_origin")
    destination = result.get("destination") or result.get("resolved_destination")
    duration = result.get("duration")
    eta = result.get("eta")
    distance = result.get("distance")
    traffic = result.get("traffic")
    is_korean = _contains_hangul(origin, destination, result.get("query"))

    if is_korean:
        route_bits = []
        if origin and destination:
            route_bits.append(f"{origin}에서 {destination}까지")
        elif destination:
            route_bits.append(f"{destination}까지")

        detail_bits = []
        if duration:
            detail_bits.append(f"약 {duration} 걸립니다")
        if eta:
            detail_bits.append(f"도착 예정은 {eta}입니다")
        if distance:
            detail_bits.append(f"거리는 {distance}입니다")
        if traffic and traffic != "unknown":
            traffic_label = {
                "light": "원활",
                "moderate": "보통",
                "heavy": "혼잡",
            }.get(traffic, traffic)
            detail_bits.append(f"교통은 {traffic_label}입니다")

        if detail_bits:
            prefix = f"{route_bits[0]} " if route_bits else ""
            return prefix + ", ".join(detail_bits) + "."
        return None

    route_text = ""
    if origin and destination:
        route_text = f"From {origin} to {destination}, "
    elif destination:
        route_text = f"To {destination}, "

    detail_bits = []
    if duration:
        detail_bits.append(f"it takes about {duration}")
    if eta:
        detail_bits.append(f"arrival is around {eta}")
    if distance:
        detail_bits.append(f"distance is {distance}")
    if traffic and traffic != "unknown":
        detail_bits.append(f"traffic is {traffic}")

    if detail_bits:
        return route_text + ", ".join(detail_bits) + "."
    return None


def _summarize_directions_result(result: dict) -> str | None:
    if result.get("status") != "success":
        return None

    origin = result.get("origin")
    destination = result.get("destination")
    duration = result.get("duration")
    distance = result.get("distance")
    route_summary = result.get("route_summary")
    is_korean = _contains_hangul(origin, destination)

    if is_korean:
        bits = []
        if origin and destination:
            bits.append(f"{origin}에서 {destination}까지 안내합니다")
        elif destination:
            bits.append(f"{destination}까지 안내합니다")
        if duration:
            bits.append(f"예상 시간은 {duration}입니다")
        if distance:
            bits.append(f"거리는 {distance}입니다")
        if route_summary:
            bits.append(f"주요 경로는 {route_summary}입니다")
        if bits:
            return ", ".join(bits) + "."
        return None

    bits = []
    if origin and destination:
        bits.append(f"Navigating from {origin} to {destination}")
    elif destination:
        bits.append(f"Navigating to {destination}")
    if duration:
        bits.append(f"ETA is {duration}")
    if distance:
        bits.append(f"distance is {distance}")
    if route_summary:
        bits.append(f"via {route_summary}")
    if bits:
        return ", ".join(bits) + "."
    return None


def _normalize_client_context(raw_context: object) -> str | None:
    if not isinstance(raw_context, str):
        return None

    normalized = " ".join(raw_context.split())
    if not normalized:
        return None

    return normalized[:500]


def _merge_text_with_context(text: str, client_context: str | None) -> str:
    if not client_context:
        return text

    return (
        f"{client_context}\n\n"
        "User request follows. Use the client location context when it is relevant.\n"
        f"{text}"
    )


def _has_visible_parts(event) -> bool:
    if not event.content or not event.content.parts:
        return False

    for part in event.content.parts:
        if part.function_call:
            return True
        if (
            part.inline_data
            and part.inline_data.mime_type
            and "audio" in part.inline_data.mime_type
        ):
            return True
        if getattr(part, "text", None) and getattr(part, "thought", False) is not True:
            return True

    return False


def _log_event_debug(event) -> None:
    """Log detailed event info for debugging tool call responses."""
    parts_info = []
    if event.content and event.content.parts:
        for part in event.content.parts:
            if part.inline_data:
                parts_info.append(
                    f"inline_data({part.inline_data.mime_type}, "
                    f"{len(part.inline_data.data) if part.inline_data.data else 0}b)"
                )
            elif getattr(part, "text", None):
                thought = getattr(part, "thought", False)
                parts_info.append(
                    f"text(thought={thought}, len={len(part.text)}, "
                    f"preview={part.text[:80]!r})"
                )
            elif part.function_call:
                parts_info.append(f"function_call({part.function_call.name})")
            elif part.function_response:
                parts_info.append(f"function_response({part.function_response.name})")
            else:
                parts_info.append(f"unknown_part({type(part).__name__})")

    out_tx = getattr(event, "output_transcription", None)
    in_tx = getattr(event, "input_transcription", None)

    logger.info(
        "EVENT: author=%s role=%s is_final=%s out_tx=%s in_tx=%s parts=[%s]",
        getattr(event, "author", "N/A"),
        event.content.role if event.content else "N/A",
        event.is_final_response(),
        bool(out_tx),
        bool(in_tx),
        ", ".join(parts_info) if parts_info else "EMPTY",
    )


@router.websocket("/ws/mobile/{user_id}")
async def mobile_voice_stream(websocket: WebSocket, user_id: str):
    """Bidirectional audio streaming between Flutter app and Gemini Live API."""
    await websocket.accept()
    logger.info("Mobile client connected: user=%s", user_id)

    session = await session_service.create_session(
        app_name=APP_NAME, user_id=user_id
    )
    session_id = session.id
    logger.info("Session created: %s", session_id)

    requested_conversation_id = websocket.query_params.get("conversation_id")
    live_queue = LiveRequestQueue()
    turn_controller = (
        TurnController(conversation_id=requested_conversation_id)
        if requested_conversation_id
        else TurnController()
    )
    send_lock = asyncio.Lock()
    new_user_turn = asyncio.Event()
    duck_timer_task: asyncio.Task | None = None
    ducked_assistant_turn_id: str | None = None
    client_context: str | None = None
    audio_context_sent = False

    async def send_client(payload: dict) -> None:
        payload.setdefault("conversation_id", turn_controller.conversation_id)
        async with send_lock:
            await websocket.send_json(payload)

    async def commit_user_turn_if_needed() -> str | None:
        snapshot = turn_controller.commit_user_turn()
        if not snapshot:
            return None

        await send_client(
            {
                "type": "transcript_final",
                "turn_id": snapshot.turn_id,
                "role": snapshot.role,
                "text": snapshot.text,
            }
        )
        await send_client(
            {
                "type": "turn_committed",
                "turn_id": snapshot.turn_id,
                "role": snapshot.role,
                "status": "completed",
            }
        )
        return snapshot.turn_id

    async def ensure_assistant_turn_started() -> str:
        await commit_user_turn_if_needed()
        turn_id, created = turn_controller.ensure_assistant_turn()
        if created:
            turn_controller.clear_assistant_block()
            await send_client(
                {
                    "type": "turn_started",
                    "turn_id": turn_id,
                    "parent_turn_id": turn_controller.current_assistant_parent_turn_id,
                    "role": "assistant",
                }
            )
        return turn_id

    async def cancel_assistant_turn(reason: str) -> None:
        nonlocal duck_timer_task, ducked_assistant_turn_id
        if duck_timer_task:
            duck_timer_task.cancel()
            duck_timer_task = None
        ducked_assistant_turn_id = None
        snapshot = turn_controller.cancel_assistant_turn()
        if not snapshot:
            return

        await send_client(
            {
                "type": "assistant_cancelled",
                "turn_id": snapshot.turn_id,
                "role": snapshot.role,
                "reason": reason,
                "text": snapshot.text,
            }
        )
        await send_client(
            {
                "type": "turn_committed",
                "turn_id": snapshot.turn_id,
                "role": snapshot.role,
                "status": "cancelled",
            }
        )

    async def finalize_assistant_turn(status: str = "completed") -> None:
        nonlocal duck_timer_task, ducked_assistant_turn_id
        if duck_timer_task:
            duck_timer_task.cancel()
            duck_timer_task = None
        ducked_assistant_turn_id = None
        snapshot = turn_controller.complete_assistant_turn()
        if not snapshot:
            return

        if snapshot.text:
            await send_client(
                {
                    "type": "transcript_final",
                    "turn_id": snapshot.turn_id,
                    "role": snapshot.role,
                    "text": snapshot.text,
                }
            )
        await send_client(
            {
                "type": "turn_committed",
                "turn_id": snapshot.turn_id,
                "role": snapshot.role,
                "status": status,
            }
        )

    async def send_assistant_duck(reason: str) -> None:
        nonlocal duck_timer_task, ducked_assistant_turn_id
        if not turn_controller.current_assistant_turn_id:
            return
        if ducked_assistant_turn_id == turn_controller.current_assistant_turn_id:
            return

        ducked_assistant_turn_id = turn_controller.current_assistant_turn_id
        await send_client(
            {
                "type": "assistant_duck",
                "turn_id": ducked_assistant_turn_id,
                "role": "assistant",
                "reason": reason,
            }
        )

        async def restore_if_not_confirmed(expected_turn_id: str) -> None:
            nonlocal duck_timer_task, ducked_assistant_turn_id
            try:
                await asyncio.sleep(0.35)
            except asyncio.CancelledError:
                return

            if (
                ducked_assistant_turn_id == expected_turn_id
                and turn_controller.current_assistant_turn_id == expected_turn_id
            ):
                await send_client(
                    {
                        "type": "assistant_resumed",
                        "turn_id": expected_turn_id,
                        "role": "assistant",
                        "reason": "false_onset",
                    }
                )
                ducked_assistant_turn_id = None
            duck_timer_task = None

        if duck_timer_task:
            duck_timer_task.cancel()
        duck_timer_task = asyncio.create_task(
            restore_if_not_confirmed(ducked_assistant_turn_id)
        )

    run_config = RunConfig(
        response_modalities=["AUDIO"],
        output_audio_transcription=types.AudioTranscriptionConfig(),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Aoede"
                )
            )
        ),
    )

    async def forward_agent_events():
        pending_tool_name: str | None = None
        pending_tool_args: dict = {}
        got_audio_after_tool = False
        turn_complete_count = 0
        already_nudged = False

        try:
            async for event in runner.run_live(
                session=session,
                live_request_queue=live_queue,
                run_config=run_config,
            ):
                _log_event_debug(event)

                if new_user_turn.is_set():
                    new_user_turn.clear()
                    pending_tool_name = None
                    pending_tool_args = {}
                    got_audio_after_tool = False
                    turn_complete_count = 0
                    already_nudged = False

                input_texts = _extract_transcription_texts(
                    getattr(event, "input_transcription", None)
                )
                if input_texts:
                    new_user_turn.set()
                    already_nudged = False
                    if turn_controller.current_assistant_turn_id:
                        if (
                            ducked_assistant_turn_id
                            == turn_controller.current_assistant_turn_id
                        ):
                            await cancel_assistant_turn("barge_in_confirmed")
                            pending_tool_name = None
                            pending_tool_args = {}
                            got_audio_after_tool = False
                            turn_complete_count = 0
                        else:
                            await send_assistant_duck("user_onset")

                    for text in input_texts:
                        snapshot = turn_controller.update_user_partial(text)
                        await send_client(
                            {
                                "type": "transcript_partial",
                                "turn_id": snapshot.turn_id,
                                "role": snapshot.role,
                                "text": snapshot.text,
                            }
                        )

                output_texts = _extract_transcription_texts(
                    getattr(event, "output_transcription", None)
                )
                if output_texts and turn_controller.should_block_assistant_output():
                    logger.debug("Dropping blocked assistant transcription")
                    output_texts = []

                for text in output_texts:
                    turn_id = await ensure_assistant_turn_started()
                    snapshot = turn_controller.update_assistant_partial(text)
                    await send_client(
                        {
                            "type": "transcript_partial",
                            "turn_id": turn_id,
                            "role": snapshot.role,
                            "text": snapshot.text,
                        }
                    )

                sent_audio = False
                sent_visible_part = False

                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.function_call:
                            if turn_controller.should_block_assistant_output():
                                logger.debug("Dropping blocked tool call")
                                continue

                            turn_id = await ensure_assistant_turn_started()
                            pending_tool_name = part.function_call.name
                            pending_tool_args = (
                                dict(part.function_call.args)
                                if part.function_call.args
                                else {}
                            )
                            got_audio_after_tool = False
                            turn_complete_count = 0
                            await send_client(
                                {
                                    "type": "tool_call",
                                    "turn_id": turn_id,
                                    "name": pending_tool_name,
                                    "args": pending_tool_args,
                                }
                            )
                            sent_visible_part = True
                            continue

                        if (
                            part.inline_data
                            and part.inline_data.mime_type
                            and "audio" in part.inline_data.mime_type
                        ):
                            if turn_controller.should_block_assistant_output():
                                logger.debug("Dropping blocked assistant audio")
                                continue

                            turn_id = await ensure_assistant_turn_started()
                            await send_client(
                                {
                                    "type": "audio",
                                    "turn_id": turn_id,
                                    "seq": turn_controller.next_audio_seq(turn_id),
                                    "data": base64.b64encode(
                                        part.inline_data.data
                                    ).decode(),
                                    "mime_type": part.inline_data.mime_type,
                                }
                            )
                            got_audio_after_tool = True
                            sent_audio = True
                            sent_visible_part = True
                            continue

                        if getattr(part, "text", None):
                            if getattr(part, "thought", False) is True:
                                logger.debug("Skipping thought: %s", part.text[:80])
                                continue
                            if output_texts:
                                continue
                            if turn_controller.should_block_assistant_output():
                                logger.debug("Dropping blocked assistant text")
                                continue

                            turn_id = await ensure_assistant_turn_started()
                            snapshot = turn_controller.update_assistant_partial(
                                part.text
                            )
                            await send_client(
                                {
                                    "type": "transcript_partial",
                                    "turn_id": turn_id,
                                    "role": snapshot.role,
                                    "text": snapshot.text,
                                }
                            )
                            sent_visible_part = True

                if (
                    event.is_final_response()
                    and pending_tool_name
                    and not already_nudged
                ):
                    turn_complete_count += 1
                    if turn_complete_count >= 2 and not got_audio_after_tool:
                        logger.info(
                            "FALLBACK: No audio after tool %s. Completing turn server-side.",
                            pending_tool_name,
                        )
                        result = _execute_tool(pending_tool_name, pending_tool_args)
                        if result:
                            turn_id = await ensure_assistant_turn_started()
                            summary = _tool_result_summary(
                                pending_tool_name,
                                result,
                            )
                            snapshot = turn_controller.update_assistant_partial(
                                summary
                            )
                            await send_client(
                                {
                                    "type": "tool_finished",
                                    "turn_id": turn_id,
                                    "name": pending_tool_name,
                                    "summary": summary,
                                }
                            )
                            await send_client(
                                {
                                    "type": "transcript_partial",
                                    "turn_id": turn_id,
                                    "role": snapshot.role,
                                    "text": snapshot.text,
                                }
                            )
                            turn_controller.block_assistant_output(1.5)
                            await finalize_assistant_turn()
                        already_nudged = True
                        pending_tool_name = None
                        pending_tool_args = {}
                        got_audio_after_tool = False
                        turn_complete_count = 0

                has_transcription = bool(input_texts) or bool(output_texts)
                if (
                    event.is_final_response()
                    and not has_transcription
                    and not sent_visible_part
                    and not _has_visible_parts(event)
                ):
                    await finalize_assistant_turn()

        except Exception as exc:
            logger.exception("Agent event error: %s", exc)
            try:
                await send_client({"type": "error", "message": str(exc)})
            except Exception:
                pass

    async def process_client_messages():
        try:
            while True:
                raw = await websocket.receive_text()
                msg = json.loads(raw)
                msg_type = msg.get("type", "")

                if msg_type in {"audio", "audio_chunk"}:
                    if client_context and not audio_context_sent:
                        live_queue.send(
                            LiveRequest(
                                content=types.Content(
                                    role="user",
                                    parts=[types.Part(text=client_context)],
                                )
                            )
                        )
                        audio_context_sent = True

                    audio_bytes = base64.b64decode(msg["data"])
                    live_queue.send(
                        LiveRequest(
                            blob=types.Blob(
                                data=audio_bytes,
                                mime_type="audio/pcm;rate=16000",
                            )
                        )
                    )
                    continue

                if msg_type == "context_update":
                    client_context = _normalize_client_context(msg.get("context"))
                    if turn_controller.current_user_turn_id is None:
                        audio_context_sent = False
                    continue

                if msg_type in {"text", "text_turn"}:
                    text = msg.get("text", "").strip()
                    if not text:
                        continue

                    if turn_controller.current_assistant_turn_id:
                        await cancel_assistant_turn("text_override")

                    new_user_turn.set()
                    snapshot = turn_controller.start_text_turn(text)
                    await send_client(
                        {
                            "type": "transcript_final",
                            "turn_id": snapshot.turn_id,
                            "role": snapshot.role,
                            "text": snapshot.text,
                        }
                    )
                    await send_client(
                        {
                            "type": "turn_committed",
                            "turn_id": snapshot.turn_id,
                            "role": snapshot.role,
                            "status": "completed",
                        }
                    )
                    live_queue.send(
                        LiveRequest(
                            content=types.Content(
                                role="user",
                                parts=[
                                    types.Part(
                                        text=_merge_text_with_context(
                                            text,
                                            client_context,
                                        )
                                    )
                                ],
                            )
                        )
                    )
                    live_queue.send(LiveRequest(end_of_turn=True))
                    audio_context_sent = False
                    continue

                if msg_type == "end_turn":
                    live_queue.send(LiveRequest(end_of_turn=True))
                    audio_context_sent = False

        except WebSocketDisconnect:
            logger.info("Client disconnected: user=%s", user_id)
        except Exception as exc:
            logger.exception("Client message error: %s", exc)

    try:
        await send_client(
            {
                "type": "session_ready",
                "session_id": session_id,
            }
        )
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
        if duck_timer_task:
            duck_timer_task.cancel()
        live_queue.close()
        logger.info("Session ended: user=%s session=%s", user_id, session_id)
