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


if __name__ == "__main__":
    unittest.main()
