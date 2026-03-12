"""In-process reminder scheduler.

Manages user-set reminders and fires them at the scheduled time by
injecting a prompt into the user's active Gemini Live session via
the WebSocket registry.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from google.adk.agents.live_request_queue import LiveRequest
from google.genai import types

from services.ws_registry import ws_registry

logger = logging.getLogger(__name__)


@dataclass
class Reminder:
    """A single scheduled reminder."""

    id: str
    user_id: str
    message: str
    fire_at: datetime  # UTC
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    fired: bool = False
    cancelled: bool = False

    @property
    def remaining_seconds(self) -> float:
        delta = self.fire_at - datetime.now(timezone.utc)
        return max(delta.total_seconds(), 0)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "message": self.message,
            "fire_at": self.fire_at.isoformat(),
            "remaining_seconds": round(self.remaining_seconds),
            "status": "cancelled" if self.cancelled else ("fired" if self.fired else "pending"),
        }


class SchedulerService:
    """Manages reminders and fires them via the WebSocket registry.

    All reminders live in-memory. On server restart they are lost.
    Production: persist to Firestore.
    """

    def __init__(self) -> None:
        self._reminders: dict[str, Reminder] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Called on app startup."""
        self._running = True
        logger.info("SchedulerService started")

    async def stop(self) -> None:
        """Cancel all pending timers on shutdown."""
        self._running = False
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
        logger.info("SchedulerService stopped")

    # ------------------------------------------------------------------
    # Public API (called by reminder_tools)
    # ------------------------------------------------------------------

    def add_reminder(
        self,
        user_id: str,
        message: str,
        fire_at: datetime,
    ) -> Reminder:
        """Schedule a new reminder.
        Includes deduplication: if a pending reminder with the same
        user_id and message already exists within a 60-second window
        of the requested fire_at, the existing one is returned instead.

        Args:
            user_id: Owner of the reminder.
            message: What to remind about.
            fire_at: UTC datetime when to fire.
            The created (or existing) Reminder object.
        """
        # Dedup: reject near-identical reminders
        for existing in self._reminders.values():
            if (
                existing.user_id == user_id
                and existing.message == message
                and not existing.fired
                and not existing.cancelled
                and abs((existing.fire_at - fire_at).total_seconds()) < 60
            ):
                logger.info(
                    "Reminder deduped: existing id=%s matches message=%r",
                    existing.id,
                    message,
                )
                return existing
        reminder_id = str(uuid.uuid4())[:8]
        reminder = Reminder(
            id=reminder_id,
            user_id=user_id,
            message=message,
            fire_at=fire_at,
        )
        self._reminders[reminder_id] = reminder
        task = asyncio.create_task(self._wait_and_fire(reminder))
        self._tasks[reminder_id] = task
        logger.info(
            "Reminder scheduled: id=%s user=%s fire_at=%s message=%r",
            reminder_id,
            user_id,
            fire_at.isoformat(),
            message,
        )
        return reminder

    def cancel_reminder(self, reminder_id: str) -> bool:
        """Cancel a pending reminder by ID.

        Returns True if cancelled, False if not found or already fired.
        """
        reminder = self._reminders.get(reminder_id)
        if not reminder or reminder.fired or reminder.cancelled:
            return False

        reminder.cancelled = True
        task = self._tasks.pop(reminder_id, None)
        if task:
            task.cancel()

        logger.info("Reminder cancelled: id=%s", reminder_id)
        return True

    def cancel_all_reminders(self, user_id: str) -> int:
        """Cancel ALL pending reminders for a user.

        Returns the number of reminders cancelled.
        """
        cancelled_count = 0
        for reminder in list(self._reminders.values()):
            if (
                reminder.user_id == user_id
                and not reminder.fired
                and not reminder.cancelled
            ):
                reminder.cancelled = True
                task = self._tasks.pop(reminder.id, None)
                if task:
                    task.cancel()
                cancelled_count += 1

        if cancelled_count:
            logger.info(
                "Cancelled %d reminder(s) for user %s",
                cancelled_count,
                user_id,
            )
        return cancelled_count

    def list_reminders(self, user_id: str) -> list[dict]:
        """List all reminders for a user (active and recent)."""
        return [
            r.to_dict()
            for r in self._reminders.values()
            if r.user_id == user_id and not r.cancelled
        ]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _wait_and_fire(self, reminder: Reminder) -> None:
        """Sleep until fire_at, then inject a proactive prompt."""
        try:
            delay = reminder.remaining_seconds
            if delay > 0:
                logger.info(
                    "Reminder %s: sleeping %.1fs",
                    reminder.id,
                    delay,
                )
                await asyncio.sleep(delay)

            if reminder.cancelled or not self._running:
                return

            reminder.fired = True
            self._tasks.pop(reminder.id, None)

            await self._deliver_reminder(reminder)

        except asyncio.CancelledError:
            logger.debug("Reminder %s timer cancelled", reminder.id)
        except Exception:
            logger.exception("Reminder %s fire error", reminder.id)

    async def _deliver_reminder(self, reminder: Reminder) -> None:
        """Push the reminder to the user's active WebSocket session."""
        entry = ws_registry.get(reminder.user_id)
        if not entry:
            logger.warning(
                "Reminder %s fired but user %s is not connected. Skipping.",
                reminder.id,
                reminder.user_id,
            )
            return

        # 1) Notify mobile that a proactive message is incoming
        try:
            await entry.send_fn({
                "type": "proactive_nudge",
                "reminder_id": reminder.id,
                "message": reminder.message,
            })
        except Exception:
            logger.exception("Failed to send proactive_nudge for %s", reminder.id)

        # 2) Inject into Gemini Live session so the agent speaks naturally
        prompt = (
            "[System: Reminder Triggered] "
            f"The user previously asked you to remind them about: '{reminder.message}'. "
            "This reminder is now due. Please proactively speak to the user and "
            "deliver this reminder in a natural, friendly way. "
            "Do not say 'system reminder' — just talk to the user as if you remembered on your own."
        )
        try:
            entry.live_queue.send(
                LiveRequest(
                    content=types.Content(
                        role="user",
                        parts=[types.Part(text=prompt)],
                    )
                )
            )
            entry.live_queue.send(LiveRequest(end_of_turn=True))
            logger.info(
                "Reminder %s delivered to user %s via live_queue",
                reminder.id,
                reminder.user_id,
            )
        except Exception:
            logger.exception(
                "Failed to inject reminder %s into live_queue",
                reminder.id,
            )


# Module-level singleton
scheduler_service = SchedulerService()