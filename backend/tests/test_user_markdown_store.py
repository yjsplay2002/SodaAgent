import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.user_markdown_store import UserMarkdownStore


class UserMarkdownStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = UserMarkdownStore(base_dir=self.temp_dir.name)
        self.user_id = "user-test-123"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_add_todo_persists_single_markdown_document(self):
        todo = self.store.add_todo(
            user_id=self.user_id,
            title="오늘 배포 준비하기",
            details="릴리즈 노트와 체크리스트 정리",
        )

        path = Path(self.temp_dir.name) / f"{self.user_id}.md"
        self.assertTrue(path.exists())

        raw = path.read_text(encoding="utf-8")
        self.assertIn("# User Memory: user-test-123", raw)
        self.assertIn("```json", raw)
        self.assertEqual(todo["status"], "todo")
        self.assertIn(todo["priority"], {"high", "medium", "low"})

    def test_status_change_is_recorded_in_history(self):
        todo = self.store.add_todo(
            user_id=self.user_id,
            title="코드 리뷰 보내기",
        )

        updated = self.store.update_todo_status(
            user_id=self.user_id,
            todo_id=todo["id"],
            status="in_progress",
            note="리뷰 초안 작성 시작",
        )

        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["status"], "in_progress")

        history = self.store.get_todo_history(self.user_id, todo["id"])
        self.assertIsNotNone(history)
        assert history is not None
        self.assertEqual(len(history), 2)
        self.assertEqual(history[-1]["from_status"], "todo")
        self.assertEqual(history[-1]["to_status"], "in_progress")

    def test_search_filters_related_todos(self):
        self.store.add_todo(
            user_id=self.user_id,
            title="Buy groceries",
            details="milk and bread",
            category="shopping",
        )
        self.store.add_todo(
            user_id=self.user_id,
            title="Prepare sprint demo",
            details="backend todo agent",
            category="work",
        )

        matches = self.store.search_todos(self.user_id, "sprint backend")

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["category"], "work")

    def test_scheduled_todo_persists_schedule_metadata(self):
        todo = self.store.add_todo(
            user_id=self.user_id,
            title="Take vitamins",
            cron="*/5 * * * *",
            phone_number="+821012345678",
            voice_message="비타민 먹을 시간이에요.",
            schedule_timezone="Asia/Seoul",
        )

        self.assertIsNotNone(todo["schedule"])
        assert todo["schedule"] is not None
        self.assertEqual(todo["schedule"]["cron"], "*/5 * * * *")
        self.assertEqual(todo["schedule"]["timezone"], "Asia/Seoul")

        scheduled = self.store.list_scheduled_todos(self.user_id)
        self.assertEqual(len(scheduled), 1)
        self.assertEqual(scheduled[0]["id"], todo["id"])

    def test_record_todo_schedule_delivery_updates_history(self):
        todo = self.store.add_todo(
            user_id=self.user_id,
            title="Stand up and stretch",
            cron="0 9 * * *",
        )

        updated = self.store.record_todo_schedule_delivery(
            user_id=self.user_id,
            todo_id=todo["id"],
            occurrence_at="2026-03-16T00:00:00+00:00",
            delivered_at="2026-03-16T00:00:10+00:00",
            channel="phone_call",
            delivery_status="success",
            call_sid="CA123",
        )

        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["schedule"]["last_delivery_channel"], "phone_call")
        self.assertEqual(updated["schedule"]["last_call_sid"], "CA123")
        self.assertEqual(updated["history"][-1]["action"], "scheduled_delivery")


if __name__ == "__main__":
    unittest.main()
