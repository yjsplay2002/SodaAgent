"""Registry of active WebSocket connections per user.

Allows the scheduler service to push proactive messages to connected
users by injecting prompts into their Gemini Live API queues.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class ConnectionEntry:
    """Tracks a single user's active WebSocket connection."""

    user_id: str
    send_fn: Callable[[dict], Awaitable[None]]
    live_queue: Any  # LiveRequestQueue — kept as Any to avoid import cycle
    connected_at: float = field(default_factory=lambda: __import__('time').time())


class WebSocketRegistry:
    """Global registry of connected mobile clients.

    Thread-safe via asyncio (single event loop). No locks needed.
    """

    def __init__(self) -> None:
        self._connections: dict[str, ConnectionEntry] = {}

    def register(
        self,
        user_id: str,
        send_fn: Callable[[dict], Awaitable[None]],
        live_queue: Any,
    ) -> None:
        """Register a user's active WebSocket connection."""
        self._connections[user_id] = ConnectionEntry(
            user_id=user_id,
            send_fn=send_fn,
            live_queue=live_queue,
        )
        logger.info("WS Registry: registered user=%s (total=%d)", user_id, len(self._connections))

    def unregister(self, user_id: str) -> None:
        """Remove a user's connection from the registry."""
        removed = self._connections.pop(user_id, None)
        if removed:
            logger.info("WS Registry: unregistered user=%s (total=%d)", user_id, len(self._connections))

    def get(self, user_id: str) -> ConnectionEntry | None:
        """Look up a user's active connection."""
        return self._connections.get(user_id)

    def is_connected(self, user_id: str) -> bool:
        return user_id in self._connections

    @property
    def connected_users(self) -> list[str]:
        return list(self._connections.keys())

    @property
    def count(self) -> int:
        return len(self._connections)


# Module-level singleton
ws_registry = WebSocketRegistry()