"""Proactive trigger evaluation engine for scheduled todo voice delivery."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from croniter import croniter

try:
    from google.adk.agents.live_request_queue import LiveRequest
    from google.genai import types
except ModuleNotFoundError:
    class LiveRequest:  # pragma: no cover - lightweight test fallback
        def __init__(self, content=None, end_of_turn: bool = False):
            self.content = content
            self.end_of_turn = end_of_turn

    class _FallbackPart:  # pragma: no cover - lightweight test fallback
        def __init__(self, text: str | None = None):
            self.text = text

    class _FallbackContent:  # pragma: no cover - lightweight test fallback
        def __init__(self, role: str | None = None, parts: list | None = None):
            self.role = role
            self.parts = parts or []

    class _FallbackTypes:  # pragma: no cover - lightweight test fallback
        Content = _FallbackContent
        Part = _FallbackPart

    types = _FallbackTypes()

from services.twilio_service import TwilioService
from services.user_markdown_store import user_markdown_store
from services.user_profile_service import user_profile_service
from services.ws_registry import ws_registry

logger = logging.getLogger(__name__)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _contains_hangul(*values: object) -> bool:
    text = " ".join(str(value) for value in values if value)
    return bool(text and any("\uac00" <= ch <= "\ud7a3" for ch in text))


class TriggerEngine:
    """Evaluates scheduled todo triggers and delivers voice notifications."""

    def __init__(self):
        self.twilio = TwilioService()

    async def evaluate_triggers(
        self,
        user_id: str | None = None,
        *,
        now: datetime | None = None,
    ) -> list[dict]:
        """Evaluate all due scheduled todos and deliver them."""
        current_time = now.astimezone(timezone.utc) if now else datetime.now(timezone.utc)
        due_todos = []
        for todo in user_markdown_store.list_scheduled_todos(user_id):
            occurrence_at = self._get_due_occurrence(todo, current_time)
            if occurrence_at is None:
                continue
            due_todos.append((todo, occurrence_at))

        results: list[dict] = []
        for todo, occurrence_at in due_todos:
            result = await self._deliver_todo(todo, occurrence_at, current_time)
            results.append(result)
        return results

    def _get_due_occurrence(
        self,
        todo: dict,
        current_time: datetime,
    ) -> datetime | None:
        schedule = todo.get("schedule") or {}
        cron_expression = schedule.get("cron")
        timezone_name = schedule.get("timezone") or "UTC"
        if not cron_expression:
            return None

        timezone_info = ZoneInfo(timezone_name)
        base_time = self._get_schedule_base(todo, timezone_info)
        next_occurrence = croniter(cron_expression, base_time).get_next(datetime)
        if next_occurrence.tzinfo is None:
            next_occurrence = next_occurrence.replace(tzinfo=timezone_info)

        next_occurrence_utc = next_occurrence.astimezone(timezone.utc)
        if next_occurrence_utc <= current_time:
            return next_occurrence_utc
        return None

    def _get_schedule_base(self, todo: dict, timezone_info: ZoneInfo) -> datetime:
        schedule = todo.get("schedule") or {}
        last_scheduled_run = _parse_datetime(schedule.get("last_scheduled_run_at"))
        if last_scheduled_run is not None:
            return last_scheduled_run.astimezone(timezone_info)

        created_at = _parse_datetime(todo.get("created_at"))
        if created_at is not None:
            return created_at.astimezone(timezone_info)

        return datetime.now(timezone_info)

    async def _deliver_todo(
        self,
        todo: dict,
        occurrence_at: datetime,
        delivered_at: datetime,
    ) -> dict:
        user_id = todo["user_id"]
        message = self._build_voice_message(todo)

        result = await self._deliver_over_live_session(user_id, todo, message, occurrence_at)
        channel = result["channel"]

        if result["status"] != "success":
            resolved_phone_number = (
                (todo.get("schedule") or {}).get("phone_number")
                or user_profile_service.get_phone_number(user_id)
            )
            result = self.twilio.initiate_message_call(
                to_number=resolved_phone_number,
                message=message,
                call_id=str(uuid.uuid4()),
            )
            channel = "phone_call"

        user_markdown_store.record_todo_schedule_delivery(
            user_id=user_id,
            todo_id=todo["id"],
            occurrence_at=occurrence_at.isoformat(),
            delivered_at=delivered_at.isoformat(),
            channel=channel,
            delivery_status=result.get("status", "error"),
            error_message=None if result.get("status") == "success" else result.get("message"),
            call_sid=result.get("call_sid"),
        )

        return {
            "type": "todo_cron",
            "todo_id": todo["id"],
            "title": todo["title"],
            "user_id": user_id,
            "occurrence_at": occurrence_at.isoformat(),
            "delivered_at": delivered_at.isoformat(),
            "channel": channel,
            "status": result.get("status", "error"),
            "message": result.get("message"),
            "call_sid": result.get("call_sid"),
        }

    async def _deliver_over_live_session(
        self,
        user_id: str,
        todo: dict,
        message: str,
        occurrence_at: datetime,
    ) -> dict:
        entry = ws_registry.get(user_id)
        if not entry:
            return {
                "status": "error",
                "channel": "live_session",
                "message": "User is not connected.",
            }

        try:
            await entry.send_fn(
                {
                    "type": "proactive_nudge",
                    "source": "todo_cron",
                    "todo_id": todo["id"],
                    "title": todo["title"],
                    "message": message,
                    "occurrence_at": occurrence_at.isoformat(),
                }
            )
            prompt = (
                "[System: Todo Cron Triggered] "
                f"The user has a scheduled todo reminder for '{todo['title']}'. "
                f"Deliver this message naturally and proactively: '{message}'. "
                "Do not mention cron jobs, automation, or system events."
            )
            entry.live_queue.send(
                LiveRequest(
                    content=types.Content(
                        role="user",
                        parts=[types.Part(text=prompt)],
                    )
                )
            )
            entry.live_queue.send(LiveRequest(end_of_turn=True))
            return {
                "status": "success",
                "channel": "live_session",
                "message": "Delivered to the active live session.",
            }
        except Exception as exc:
            logger.exception("Failed to deliver todo %s to live session", todo["id"])
            return {
                "status": "error",
                "channel": "live_session",
                "message": str(exc),
            }

    def _build_voice_message(self, todo: dict) -> str:
        schedule = todo.get("schedule") or {}
        custom_message = (schedule.get("voice_message") or "").strip()
        if custom_message:
            return custom_message

        title = (todo.get("title") or "").strip()
        details = (todo.get("details") or "").strip()
        if _contains_hangul(title, details):
            if details:
                return f"{title} 할 시간이에요. 메모는 {details}입니다."
            return f"{title} 할 시간이에요."

        if details:
            return f"It's time for {title}. Note: {details}."
        return f"It's time for {title}."
