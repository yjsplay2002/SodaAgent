import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.ws_ticket_store import WebSocketTicketStore


class WebSocketTicketStoreTest(unittest.TestCase):
    def test_issue_and_consume_is_one_time(self):
        store = WebSocketTicketStore(ttl_seconds=300)

        ticket = store.issue("firebase-uid-123")

        self.assertEqual(store.consume(ticket.token), "firebase-uid-123")
        self.assertIsNone(store.consume(ticket.token))

    def test_expired_ticket_is_rejected(self):
        store = WebSocketTicketStore(ttl_seconds=60)
        now = datetime(2026, 3, 16, tzinfo=UTC)

        with patch("services.ws_ticket_store._utcnow", return_value=now):
            ticket = store.issue("firebase-uid-123")

        with patch(
            "services.ws_ticket_store._utcnow",
            return_value=now + timedelta(seconds=61),
        ):
            self.assertIsNone(store.consume(ticket.token))


if __name__ == "__main__":
    unittest.main()
