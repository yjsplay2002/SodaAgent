"""Turn-scoped conversation state for live voice sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
import uuid


def _new_turn_id(role: str) -> str:
    return f"{role}-{uuid.uuid4().hex[:12]}"


@dataclass
class TurnSnapshot:
    turn_id: str
    role: str
    text: str = ""


@dataclass
class TurnController:
    """Tracks the active user/assistant turns for one live conversation."""

    conversation_id: str = field(
        default_factory=lambda: f"conv-{uuid.uuid4().hex[:12]}"
    )
    current_user_turn_id: str | None = None
    current_user_partial: str = ""
    last_user_turn_id: str | None = None
    current_assistant_turn_id: str | None = None
    current_assistant_partial: str = ""
    current_assistant_parent_turn_id: str | None = None
    _audio_seq: dict[str, int] = field(default_factory=dict)
    _blocked_assistant_until: float = 0.0

    def ensure_user_turn(self) -> tuple[str, bool]:
        if self.current_user_turn_id:
            return self.current_user_turn_id, False
        self.current_user_turn_id = _new_turn_id("user")
        self.current_user_partial = ""
        return self.current_user_turn_id, True

    def start_text_turn(self, text: str) -> TurnSnapshot:
        turn_id = _new_turn_id("user")
        self.current_user_turn_id = None
        self.current_user_partial = ""
        self.last_user_turn_id = turn_id
        return TurnSnapshot(turn_id=turn_id, role="user", text=text.strip())

    def update_user_partial(self, text: str) -> TurnSnapshot:
        turn_id, _ = self.ensure_user_turn()
        self.current_user_partial = text.strip()
        return TurnSnapshot(
            turn_id=turn_id,
            role="user",
            text=self.current_user_partial,
        )

    def commit_user_turn(self) -> TurnSnapshot | None:
        if not self.current_user_turn_id:
            return None
        snapshot = TurnSnapshot(
            turn_id=self.current_user_turn_id,
            role="user",
            text=self.current_user_partial.strip(),
        )
        self.last_user_turn_id = snapshot.turn_id
        self.current_user_turn_id = None
        self.current_user_partial = ""
        return snapshot if snapshot.text else None

    def ensure_assistant_turn(self) -> tuple[str, bool]:
        if self.current_assistant_turn_id:
            return self.current_assistant_turn_id, False
        self.current_assistant_turn_id = _new_turn_id("assistant")
        self.current_assistant_partial = ""
        self.current_assistant_parent_turn_id = self.last_user_turn_id
        return self.current_assistant_turn_id, True

    def update_assistant_partial(self, text: str) -> TurnSnapshot:
        turn_id, _ = self.ensure_assistant_turn()
        self.current_assistant_partial = text.strip()
        return TurnSnapshot(
            turn_id=turn_id,
            role="assistant",
            text=self.current_assistant_partial,
        )

    def cancel_assistant_turn(
        self,
        *,
        block_for_seconds: float = 0.6,
    ) -> TurnSnapshot | None:
        if not self.current_assistant_turn_id:
            return None
        snapshot = TurnSnapshot(
            turn_id=self.current_assistant_turn_id,
            role="assistant",
            text=self.current_assistant_partial.strip(),
        )
        self.current_assistant_turn_id = None
        self.current_assistant_partial = ""
        self.current_assistant_parent_turn_id = None
        self._blocked_assistant_until = time.monotonic() + block_for_seconds
        return snapshot

    def complete_assistant_turn(self) -> TurnSnapshot | None:
        if not self.current_assistant_turn_id:
            return None
        snapshot = TurnSnapshot(
            turn_id=self.current_assistant_turn_id,
            role="assistant",
            text=self.current_assistant_partial.strip(),
        )
        self.current_assistant_turn_id = None
        self.current_assistant_partial = ""
        self.current_assistant_parent_turn_id = None
        return snapshot

    def should_block_assistant_output(self) -> bool:
        return time.monotonic() < self._blocked_assistant_until

    def clear_assistant_block(self) -> None:
        self._blocked_assistant_until = 0.0

    def block_assistant_output(self, seconds: float) -> None:
        self._blocked_assistant_until = max(
            self._blocked_assistant_until,
            time.monotonic() + seconds,
        )

    def next_audio_seq(self, turn_id: str) -> int:
        next_seq = self._audio_seq.get(turn_id, 0) + 1
        self._audio_seq[turn_id] = next_seq
        return next_seq
