"""Short-lived WebSocket tickets issued after Firebase auth succeeds."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import secrets
import threading


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class WebSocketTicket:
    token: str
    user_id: str
    expires_at: datetime


class WebSocketTicketStore:
    def __init__(self, ttl_seconds: int = 300) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._lock = threading.RLock()
        self._tickets: dict[str, WebSocketTicket] = {}

    def issue(self, user_id: str) -> WebSocketTicket:
        with self._lock:
            self._purge_expired_locked()
            token = secrets.token_urlsafe(32)
            ticket = WebSocketTicket(
                token=token,
                user_id=user_id,
                expires_at=_utcnow() + self._ttl,
            )
            self._tickets[token] = ticket
            return ticket

    def consume(self, token: str | None) -> str | None:
        if not token:
            return None

        with self._lock:
            self._purge_expired_locked()
            ticket = self._tickets.pop(token, None)
            if not ticket:
                return None
            if ticket.expires_at <= _utcnow():
                return None
            return ticket.user_id

    def _purge_expired_locked(self) -> None:
        now = _utcnow()
        expired = [
            token for token, ticket in self._tickets.items()
            if ticket.expires_at <= now
        ]
        for token in expired:
            self._tickets.pop(token, None)


ws_ticket_store = WebSocketTicketStore()
