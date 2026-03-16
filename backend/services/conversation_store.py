"""In-memory conversation catalog for session recovery and session list APIs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import re
import threading
import uuid
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_conversation_id() -> str:
    return f"conv-{uuid.uuid4().hex[:12]}"


def _truncate(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+|[가-힣]+", text.lower())
        if token not in _STOPWORDS
    }


_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "be",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "please",
    "the",
    "to",
    "what",
    "when",
    "where",
    "with",
    "좀",
    "그",
    "그거",
    "그냥",
    "나",
    "내",
    "다시",
    "더",
    "좀더",
    "뭐",
    "어디",
    "얼마",
    "오늘",
    "이",
    "이거",
    "저",
    "좀",
}

_FOLLOW_UP_PATTERNS = [
    r"\bcontinue\b",
    r"\bagain\b",
    r"\bearlier\b",
    r"\bprevious\b",
    r"\bsame (?:one|thing)\b",
    r"\bthat\b",
    r"\bthere\b",
    r"\bit\b",
    r"이어서",
    r"아까",
    r"방금",
    r"계속",
    r"그거",
    r"그 일정",
    r"그 노래",
    r"거기",
]

_WEATHER_PATTERNS = [
    r"\bweather\b",
    r"\bforecast\b",
    r"\brain\b",
    r"\btemperature\b",
    r"\bhumid",
    r"날씨",
    r"기온",
    r"비",
]

_NAVIGATION_PATTERNS = [
    r"\beta\b",
    r"\bdirections?\b",
    r"\bnavigation\b",
    r"\btraffic\b",
    r"\broute\b",
    r"\bhow long\b",
    r"\bnearby\b",
    r"\bplace",
    r"길안내",
    r"네비",
    r"내비",
    r"교통",
    r"얼마나 걸",
    r"몇 분",
    r"근처",
]

_CALENDAR_PATTERNS = [
    r"\bcalendar\b",
    r"\bmeeting\b",
    r"\bschedule\b",
    r"\bevent\b",
    r"\bappointment\b",
    r"일정",
    r"미팅",
    r"약속",
    r"회의",
    r"캘린더",
]

_MUSIC_PATTERNS = [
    r"\bmusic\b",
    r"\bplay\b",
    r"\bsong\b",
    r"\btrack\b",
    r"\bpause\b",
    r"노래",
    r"음악",
    r"재생",
]

_MESSAGING_PATTERNS = [
    r"\bmessage\b",
    r"\btext\b",
    r"\bsend\b",
    r"\bread\b",
    r"문자",
    r"메시지",
    r"연락",
]

_GENERAL_STANDALONE_PATTERNS = [
    r"\btime\b",
    r"\bdate\b",
    r"\bsearch\b",
    r"몇시",
    r"시간",
    r"날짜",
]


@dataclass(slots=True)
class ConversationTurn:
    turn_id: str
    role: str
    text: str
    status: str = "completed"
    is_final: bool = True
    created_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "role": self.role,
            "text": self.text,
            "status": self.status,
            "is_final": self.is_final,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True)
class ConversationRecord:
    conversation_id: str
    user_id: str
    title: str
    domain: str = "general"
    preview: str = ""
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    turns: list[ConversationTurn] = field(default_factory=list)
    turn_count: int = 0
    last_user_text: str = ""
    last_assistant_text: str = ""
    has_bound_session: bool = False
    adk_session_id: str | None = None
    adk_session: Any | None = None
    is_active: bool = False
    last_tool_name: str | None = None

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "title": self.title,
            "preview": self.preview,
            "domain": self.domain,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "turn_count": self.turn_count,
            "is_active": self.is_active,
            "has_bound_session": self.has_bound_session,
        }

    def to_detail_dict(self) -> dict[str, Any]:
        payload = self.to_summary_dict()
        payload["turns"] = [turn.to_dict() for turn in self.turns]
        return payload


@dataclass(slots=True)
class ConversationResolution:
    record: ConversationRecord
    created: bool
    reused: bool
    reason: str


class ConversationStore:
    """Tracks conversation metadata separately from ADK session storage."""

    def __init__(self):
        self._lock = threading.RLock()
        self._records_by_user: dict[str, dict[str, ConversationRecord]] = {}

    def list_conversations(self, user_id: str) -> list[dict[str, Any]]:
        with self._lock:
            records = list(self._records_for_user(user_id).values())
            records.sort(key=lambda record: record.updated_at, reverse=True)
            return [record.to_summary_dict() for record in records]

    def get_conversation(
        self, user_id: str, conversation_id: str
    ) -> dict[str, Any] | None:
        with self._lock:
            record = self._records_for_user(user_id).get(conversation_id)
            if not record:
                return None
            return record.to_detail_dict()

    def get_record(
        self, user_id: str, conversation_id: str
    ) -> ConversationRecord | None:
        with self._lock:
            return self._records_for_user(user_id).get(conversation_id)

    def resolve_for_text(
        self,
        user_id: str,
        text: str,
        preferred_conversation_id: str | None = None,
    ) -> ConversationResolution:
        normalized = " ".join(text.split())
        if preferred_conversation_id:
            return self._resolve_preferred(
                user_id=user_id,
                preferred_conversation_id=preferred_conversation_id,
                fallback_text=normalized,
            )

        with self._lock:
            records = self._sorted_records(user_id)
            if not records:
                record = self._create_record_unlocked(user_id, seed_text=normalized)
                return ConversationResolution(
                    record=record,
                    created=True,
                    reused=False,
                    reason="first_conversation",
                )

            follow_up = self._has_follow_up_signal(normalized)
            domain = self._infer_domain(normalized)
            standalone = self._is_standalone_utility(normalized, domain, follow_up)

            if standalone:
                record = self._create_record_unlocked(
                    user_id,
                    seed_text=normalized,
                    domain=domain,
                )
                return ConversationResolution(
                    record=record,
                    created=True,
                    reused=False,
                    reason="standalone_utility",
                )

            if follow_up:
                candidate = self._most_recent_continuable(records, domain=domain)
                if candidate:
                    return ConversationResolution(
                        record=candidate,
                        created=False,
                        reused=True,
                        reason="follow_up_recent_match",
                    )

            best_record, best_score = self._best_relevance_match(normalized, domain, records)
            if best_record and best_score >= 4:
                return ConversationResolution(
                    record=best_record,
                    created=False,
                    reused=True,
                    reason=f"relevance_score_{best_score}",
                )

            record = self._create_record_unlocked(user_id, seed_text=normalized, domain=domain)
            return ConversationResolution(
                record=record,
                created=True,
                reused=False,
                reason="new_conversation",
            )

    def resolve_for_audio(
        self,
        user_id: str,
        preferred_conversation_id: str | None = None,
    ) -> ConversationResolution:
        if preferred_conversation_id:
            return self._resolve_preferred(
                user_id=user_id,
                preferred_conversation_id=preferred_conversation_id,
                fallback_text="",
            )

        with self._lock:
            records = self._sorted_records(user_id)
            candidate = self._most_recent_continuable(records, domain=None)
            if candidate:
                return ConversationResolution(
                    record=candidate,
                    created=False,
                    reused=True,
                    reason="resume_recent_audio_session",
                )

            record = self._create_record_unlocked(user_id)
            return ConversationResolution(
                record=record,
                created=True,
                reused=False,
                reason="new_audio_session",
            )

    def bind_adk_session(
        self,
        user_id: str,
        conversation_id: str,
        *,
        adk_session: Any,
        adk_session_id: str,
    ) -> ConversationRecord:
        with self._lock:
            record = self._records_for_user(user_id)[conversation_id]
            record.adk_session = adk_session
            record.adk_session_id = adk_session_id
            record.has_bound_session = True
            record.is_active = True
            record.updated_at = _utcnow()
            return record

    def mark_inactive(self, user_id: str, conversation_id: str) -> None:
        with self._lock:
            record = self._records_for_user(user_id).get(conversation_id)
            if not record:
                return
            record.is_active = False
            record.updated_at = _utcnow()

    def append_turn(
        self,
        user_id: str,
        conversation_id: str,
        *,
        turn_id: str,
        role: str,
        text: str,
        status: str = "completed",
        is_final: bool = True,
    ) -> ConversationRecord | None:
        normalized = text.strip()
        if not normalized:
            return None

        with self._lock:
            record = self._records_for_user(user_id).get(conversation_id)
            if not record:
                return None

            for existing in record.turns:
                if existing.turn_id == turn_id:
                    existing.text = normalized
                    existing.status = status
                    existing.is_final = is_final
                    existing.created_at = _utcnow()
                    record.updated_at = existing.created_at
                    record.preview = _truncate(normalized, 96)
                    return record

            turn = ConversationTurn(
                turn_id=turn_id,
                role=role,
                text=normalized,
                status=status,
                is_final=is_final,
            )
            record.turns.append(turn)
            if len(record.turns) > 40:
                record.turns = record.turns[-40:]
            record.turn_count += 1
            record.updated_at = turn.created_at
            record.preview = _truncate(normalized, 96)
            if role == "user":
                record.last_user_text = normalized
                if record.turn_count == 1 and not record.title.startswith("Conversation "):
                    record.title = _truncate(normalized, 42)
                elif record.turn_count == 1:
                    record.title = _truncate(normalized, 42)
                record.domain = self._infer_domain(normalized)
            elif role in {"assistant", "model"}:
                record.last_assistant_text = normalized
            return record

    def record_tool_use(
        self,
        user_id: str,
        conversation_id: str,
        tool_name: str,
    ) -> None:
        with self._lock:
            record = self._records_for_user(user_id).get(conversation_id)
            if not record:
                return
            record.last_tool_name = tool_name
            record.domain = self._domain_from_tool(tool_name) or record.domain
            record.updated_at = _utcnow()

    def _resolve_preferred(
        self,
        *,
        user_id: str,
        preferred_conversation_id: str,
        fallback_text: str,
    ) -> ConversationResolution:
        with self._lock:
            record = self._records_for_user(user_id).get(preferred_conversation_id)
            if record:
                return ConversationResolution(
                    record=record,
                    created=False,
                    reused=True,
                    reason="preferred_conversation",
                )

            domain = self._infer_domain(fallback_text) if fallback_text else "general"
            record = self._create_record_unlocked(
                user_id=user_id,
                seed_text=fallback_text,
                domain=domain,
            )
            return ConversationResolution(
                record=record,
                created=True,
                reused=False,
                reason="preferred_missing_new",
            )

    def _records_for_user(self, user_id: str) -> dict[str, ConversationRecord]:
        return self._records_by_user.setdefault(user_id, {})

    def _sorted_records(self, user_id: str) -> list[ConversationRecord]:
        records = list(self._records_for_user(user_id).values())
        records.sort(key=lambda record: record.updated_at, reverse=True)
        return records

    def _create_record_unlocked(
        self,
        user_id: str,
        seed_text: str = "",
        domain: str | None = None,
    ) -> ConversationRecord:
        title = _truncate(seed_text, 42) if seed_text else f"Conversation {len(self._records_for_user(user_id)) + 1}"
        record = ConversationRecord(
            conversation_id=_new_conversation_id(),
            user_id=user_id,
            title=title,
            domain=domain or (self._infer_domain(seed_text) if seed_text else "general"),
            preview=_truncate(seed_text, 96) if seed_text else "",
        )
        self._records_for_user(user_id)[record.conversation_id] = record
        return record

    def _has_follow_up_signal(self, text: str) -> bool:
        lowered = text.lower()
        return any(re.search(pattern, lowered) for pattern in _FOLLOW_UP_PATTERNS)

    def _infer_domain(self, text: str) -> str:
        lowered = text.lower()
        for domain, patterns in (
            ("weather", _WEATHER_PATTERNS),
            ("navigation", _NAVIGATION_PATTERNS),
            ("calendar", _CALENDAR_PATTERNS),
            ("music", _MUSIC_PATTERNS),
            ("messaging", _MESSAGING_PATTERNS),
        ):
            if any(re.search(pattern, lowered) for pattern in patterns):
                return domain
        return "general"

    def _is_standalone_utility(
        self,
        text: str,
        domain: str,
        has_follow_up_signal: bool,
    ) -> bool:
        if has_follow_up_signal:
            return False

        lowered = text.lower()
        if domain in {"weather", "navigation"}:
            return True
        return any(
            re.search(pattern, lowered) for pattern in _GENERAL_STANDALONE_PATTERNS
        )

    def _most_recent_continuable(
        self,
        records: list[ConversationRecord],
        *,
        domain: str | None,
    ) -> ConversationRecord | None:
        now = _utcnow()
        for record in records:
            if now - record.updated_at > timedelta(hours=24):
                continue
            if domain and record.domain == domain:
                return record
            if record.domain not in {"weather", "navigation", "general"}:
                return record
            if record.domain == domain and domain not in {None, "general"}:
                return record
        return None

    def _best_relevance_match(
        self,
        text: str,
        domain: str,
        records: list[ConversationRecord],
    ) -> tuple[ConversationRecord | None, int]:
        query_tokens = _tokenize(text)
        now = _utcnow()
        best_record: ConversationRecord | None = None
        best_score = 0

        for record in records:
            score = 0
            if record.domain == domain and domain != "general":
                score += 2

            age = now - record.updated_at
            if age <= timedelta(minutes=30):
                score += 3
            elif age <= timedelta(hours=6):
                score += 2
            elif age <= timedelta(hours=24):
                score += 1

            haystack = " ".join(
                filter(
                    None,
                    [
                        record.title,
                        record.preview,
                        record.last_user_text,
                        record.last_assistant_text,
                    ],
                )
            )
            overlap = len(query_tokens & _tokenize(haystack))
            score += overlap

            if score > best_score:
                best_record = record
                best_score = score

        return best_record, best_score

    def _domain_from_tool(self, tool_name: str) -> str | None:
        if tool_name.startswith("get_current_weather") or tool_name.startswith("get_forecast"):
            return "weather"
        if tool_name in {"get_directions", "get_eta", "get_eta_from_query", "search_places"}:
            return "navigation"
        if tool_name in {"get_upcoming_events", "create_event", "get_free_slots"}:
            return "calendar"
        if tool_name in {"play_song", "pause_music", "skip_track"}:
            return "music"
        if tool_name in {"read_messages", "send_message"}:
            return "messaging"
        if tool_name == "get_vehicle_status":
            return "general"
        return None


conversation_store = ConversationStore()
