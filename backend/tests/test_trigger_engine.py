import asyncio
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.trigger_engine import TriggerEngine
from services.user_markdown_store import UserMarkdownStore
from services.ws_registry import WebSocketRegistry


class _FakeLiveQueue:
    def __init__(self):
        self.requests = []

    def send(self, request):
        self.requests.append(request)


class TriggerEngineTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = UserMarkdownStore(base_dir=self.temp_dir.name)
        self.registry = WebSocketRegistry()
        self.user_id = "user-voice-123"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_connected_user_gets_live_voice_delivery(self):
        todo = self.store.add_todo(
            user_id=self.user_id,
            title="약 먹기",
            details="저녁 식후",
            cron="* * * * *",
            schedule_timezone="Asia/Seoul",
        )
        created_at = datetime.fromisoformat(todo["created_at"])
        due_time = created_at + timedelta(minutes=1, seconds=5)

        sent_payloads = []

        async def send_fn(payload):
            sent_payloads.append(payload)

        live_queue = _FakeLiveQueue()
        self.registry.register(
            user_id=self.user_id,
            send_fn=send_fn,
            live_queue=live_queue,
        )

        engine = TriggerEngine()
        engine.twilio.initiate_message_call = Mock()

        with patch("services.trigger_engine.user_markdown_store", self.store), patch(
            "services.trigger_engine.ws_registry", self.registry
        ):
            results = asyncio.run(engine.evaluate_triggers(self.user_id, now=due_time))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["channel"], "live_session")
        self.assertEqual(results[0]["status"], "success")
        self.assertEqual(sent_payloads[0]["type"], "proactive_nudge")
        self.assertEqual(sent_payloads[0]["source"], "todo_cron")
        self.assertEqual(len(live_queue.requests), 2)
        engine.twilio.initiate_message_call.assert_not_called()

    def test_disconnected_user_gets_phone_call(self):
        todo = self.store.add_todo(
            user_id=self.user_id,
            title="Pay rent",
            details="before noon",
            cron="* * * * *",
            phone_number="+15551234567",
            schedule_timezone="UTC",
        )
        created_at = datetime.fromisoformat(todo["created_at"])
        due_time = created_at + timedelta(minutes=1, seconds=5)

        engine = TriggerEngine()
        engine.twilio.initiate_message_call = Mock(
            return_value={
                "status": "success",
                "call_sid": "CA999",
                "to": "+15551234567",
                "message": "It's time for Pay rent. Note: before noon.",
            }
        )

        with patch("services.trigger_engine.user_markdown_store", self.store), patch(
            "services.trigger_engine.ws_registry", self.registry
        ):
            results = asyncio.run(engine.evaluate_triggers(self.user_id, now=due_time))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["channel"], "phone_call")
        self.assertEqual(results[0]["status"], "success")
        engine.twilio.initiate_message_call.assert_called_once()

        stored_todo = self.store.get_todo(self.user_id, todo["id"])
        self.assertIsNotNone(stored_todo)
        assert stored_todo is not None
        self.assertEqual(stored_todo["schedule"]["last_delivery_channel"], "phone_call")
        self.assertEqual(stored_todo["schedule"]["last_call_sid"], "CA999")


if __name__ == "__main__":
    unittest.main()
