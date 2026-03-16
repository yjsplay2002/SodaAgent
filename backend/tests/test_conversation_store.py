import sys
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.conversation_store import ConversationStore


class ConversationStoreTest(unittest.TestCase):
    def setUp(self):
        self.store = ConversationStore()
        self.user_id = "user-123"

    def test_standalone_weather_query_creates_new_conversation(self):
        first = self.store.resolve_for_text(self.user_id, "내일 회의 일정 알려줘")
        self.store.append_turn(
            self.user_id,
            first.record.conversation_id,
            turn_id="user-1",
            role="user",
            text="내일 회의 일정 알려줘",
        )

        second = self.store.resolve_for_text(self.user_id, "오늘 날씨 어때?")

        self.assertTrue(second.created)
        self.assertNotEqual(
            first.record.conversation_id,
            second.record.conversation_id,
        )
        self.assertEqual(second.record.domain, "weather")

    def test_follow_up_query_resumes_recent_conversation(self):
        first = self.store.resolve_for_text(self.user_id, "다음주 미팅 일정 잡아줘")
        self.store.append_turn(
            self.user_id,
            first.record.conversation_id,
            turn_id="user-1",
            role="user",
            text="다음주 미팅 일정 잡아줘",
        )

        follow_up = self.store.resolve_for_text(self.user_id, "그거 오후로 바꿔줘")

        self.assertTrue(follow_up.reused)
        self.assertEqual(
            first.record.conversation_id,
            follow_up.record.conversation_id,
        )

    def test_explicit_preferred_conversation_wins(self):
        first = self.store.resolve_for_text(self.user_id, "엄마한테 문자 보내줘")
        preferred = self.store.resolve_for_text(
            self.user_id,
            "오늘 날씨 어때?",
            preferred_conversation_id=first.record.conversation_id,
        )

        self.assertTrue(preferred.reused)
        self.assertEqual(
            preferred.record.conversation_id,
            first.record.conversation_id,
        )

    def test_list_conversations_returns_recent_first(self):
        older = self.store.resolve_for_text(self.user_id, "노래 틀어줘")
        self.store.append_turn(
            self.user_id,
            older.record.conversation_id,
            turn_id="user-1",
            role="user",
            text="노래 틀어줘",
        )

        newer = self.store.resolve_for_text(self.user_id, "오늘 날씨 어때?")
        self.store.append_turn(
            self.user_id,
            newer.record.conversation_id,
            turn_id="user-2",
            role="user",
            text="오늘 날씨 어때?",
        )
        self.store.append_turn(
            self.user_id,
            newer.record.conversation_id,
            turn_id="assistant-2",
            role="assistant",
            text="맑고 18도입니다.",
        )
        older_record = self.store.get_record(self.user_id, older.record.conversation_id)
        newer_record = self.store.get_record(self.user_id, newer.record.conversation_id)
        assert older_record is not None
        assert newer_record is not None
        newer_record.updated_at = older_record.updated_at + timedelta(seconds=1)

        sessions = self.store.list_conversations(self.user_id)

        self.assertEqual(sessions[0]["conversation_id"], newer.record.conversation_id)
        self.assertEqual(sessions[1]["conversation_id"], older.record.conversation_id)


if __name__ == "__main__":
    unittest.main()
