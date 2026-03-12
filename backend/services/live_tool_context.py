"""Per-session context shared with live tool executions."""

from __future__ import annotations

from contextvars import ContextVar, Token

_active_session_id: ContextVar[str | None] = ContextVar(
    "active_live_session_id",
    default=None,
)
_active_user_id: ContextVar[str | None] = ContextVar(
    "active_live_user_id",
    default=None,
)
_location_by_session: dict[str, tuple[float, float]] = {}


def set_active_session(session_id: str) -> Token:
    return _active_session_id.set(session_id)


def reset_active_session(token: Token) -> None:
    _active_session_id.reset(token)


def set_active_user(user_id: str) -> Token:
    return _active_user_id.set(user_id)


def reset_active_user(token: Token) -> None:
    _active_user_id.reset(token)


def get_active_user_id() -> str | None:
    return _active_user_id.get()


def set_session_location(session_id: str, latitude: float, longitude: float) -> None:
    _location_by_session[session_id] = (latitude, longitude)


def clear_session_location(session_id: str) -> None:
    _location_by_session.pop(session_id, None)


def get_current_session_location() -> tuple[float, float] | None:
    session_id = _active_session_id.get()
    if not session_id:
        return None
    return _location_by_session.get(session_id)
