"""User-scoped Markdown storage for temporary server-side persistence.

This is an interim persistence layer until Firebase Auth + Firestore are wired in.
Each user gets a single Markdown file containing a readable summary and a canonical
JSON block that the server updates transactionally.
"""

from __future__ import annotations

import json
import re
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALID_TODO_STATUSES = {"todo", "in_progress", "review", "done"}
VALID_PRIORITIES = {"high", "medium", "low"}


class UserMarkdownStore:
    """Persists user data into one Markdown document per user."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        root = (
            Path(base_dir)
            if base_dir is not None
            else Path(__file__).resolve().parent.parent / "data" / "user_memory"
        )
        self._base_dir = root
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def add_todo(
        self,
        user_id: str,
        title: str,
        details: str | None = None,
        priority: str | None = None,
        category: str | None = None,
    ) -> dict[str, Any]:
        data = self.load_user_data(user_id)
        now = self._now()
        normalized_priority = self._normalize_priority(
            priority or self._infer_priority(title, details)
        )
        normalized_category = self._normalize_category(
            category or self._infer_category(title, details)
        )
        todo_id = f"todo-{uuid.uuid4().hex[:10]}"
        todo = {
            "id": todo_id,
            "title": title.strip(),
            "details": (details or "").strip(),
            "priority": normalized_priority,
            "category": normalized_category,
            "status": "todo",
            "created_at": now,
            "updated_at": now,
            "last_activity_at": now,
            "history": [
                {
                    "timestamp": now,
                    "action": "created",
                    "note": "Todo created",
                    "from_status": None,
                    "to_status": "todo",
                }
            ],
        }
        data["todos"].append(todo)
        self._append_activity(
            data,
            action="todo_created",
            note=f"Created todo '{todo['title']}'",
            todo_id=todo_id,
        )
        self._write_user_data(user_id, data)
        return deepcopy(todo)

    def list_todos(
        self,
        user_id: str,
        status: str | None = None,
        category: str | None = None,
        priority: str | None = None,
    ) -> list[dict[str, Any]]:
        data = self.load_user_data(user_id)
        todos = data["todos"]
        if status:
            normalized_status = self._normalize_status(status)
            todos = [todo for todo in todos if todo["status"] == normalized_status]
        if category:
            normalized_category = self._normalize_category(category)
            todos = [todo for todo in todos if todo["category"] == normalized_category]
        if priority:
            normalized_priority = self._normalize_priority(priority)
            todos = [todo for todo in todos if todo["priority"] == normalized_priority]
        self._append_activity(
            data,
            action="todo_listed",
            note="Listed todos",
            todo_id=None,
        )
        self._write_user_data(user_id, data)
        return [deepcopy(todo) for todo in todos]

    def search_todos(self, user_id: str, query: str) -> list[dict[str, Any]]:
        data = self.load_user_data(user_id)
        terms = self._normalize_text(query).split()
        todos: list[dict[str, Any]] = []
        for todo in data["todos"]:
            haystack = self._normalize_text(
                " ".join(
                    [
                        todo["title"],
                        todo.get("details", ""),
                        todo.get("category", ""),
                        todo.get("priority", ""),
                        todo.get("status", ""),
                    ]
                )
            )
            if all(term in haystack for term in terms):
                todos.append(deepcopy(todo))
        self._append_activity(
            data,
            action="todo_searched",
            note=f"Searched todos for '{query.strip()}'",
            todo_id=None,
        )
        self._write_user_data(user_id, data)
        return todos

    def get_todo(self, user_id: str, todo_id: str) -> dict[str, Any] | None:
        data = self.load_user_data(user_id)
        todo = self._find_todo(data, todo_id)
        if todo is None:
            return None
        self._append_activity(
            data,
            action="todo_viewed",
            note=f"Viewed todo '{todo['title']}'",
            todo_id=todo_id,
        )
        self._write_user_data(user_id, data)
        return deepcopy(todo)

    def update_todo_status(
        self,
        user_id: str,
        todo_id: str,
        status: str,
        note: str | None = None,
    ) -> dict[str, Any] | None:
        data = self.load_user_data(user_id)
        todo = self._find_todo(data, todo_id)
        if todo is None:
            return None
        normalized_status = self._normalize_status(status)
        previous_status = todo["status"]
        now = self._now()
        todo["status"] = normalized_status
        todo["updated_at"] = now
        todo["last_activity_at"] = now
        todo["history"].append(
            {
                "timestamp": now,
                "action": "status_changed",
                "note": note or f"Status changed to {normalized_status}",
                "from_status": previous_status,
                "to_status": normalized_status,
            }
        )
        self._append_activity(
            data,
            action="todo_status_changed",
            note=(
                f"Changed todo '{todo['title']}' from {previous_status} to "
                f"{normalized_status}"
            ),
            todo_id=todo_id,
        )
        self._write_user_data(user_id, data)
        return deepcopy(todo)

    def get_todo_history(self, user_id: str, todo_id: str) -> list[dict[str, Any]] | None:
        data = self.load_user_data(user_id)
        todo = self._find_todo(data, todo_id)
        if todo is None:
            return None
        self._append_activity(
            data,
            action="todo_history_viewed",
            note=f"Viewed history for todo '{todo['title']}'",
            todo_id=todo_id,
        )
        self._write_user_data(user_id, data)
        return deepcopy(todo["history"])

    def load_user_data(self, user_id: str) -> dict[str, Any]:
        path = self._user_path(user_id)
        if not path.exists():
            return self._empty_document(user_id)

        raw = path.read_text(encoding="utf-8")
        match = re.search(
            r"<!-- SODA_DATA_START -->\n```json\n(.*?)\n```\n<!-- SODA_DATA_END -->",
            raw,
            re.DOTALL,
        )
        if not match:
            return self._empty_document(user_id)

        try:
            parsed = json.loads(match.group(1))
        except json.JSONDecodeError:
            return self._empty_document(user_id)

        parsed.setdefault("user_id", user_id)
        parsed.setdefault("todos", [])
        parsed.setdefault("activity_log", [])
        parsed.setdefault("version", 1)
        parsed.setdefault("updated_at", self._now())
        for todo in parsed["todos"]:
            todo.setdefault("details", "")
            todo.setdefault("priority", "medium")
            todo.setdefault("category", "general")
            todo.setdefault("status", "todo")
            todo.setdefault("history", [])
        return parsed

    def _write_user_data(self, user_id: str, data: dict[str, Any]) -> None:
        data["updated_at"] = self._now()
        path = self._user_path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._render_markdown(data), encoding="utf-8")

    def _render_markdown(self, data: dict[str, Any]) -> str:
        open_todos = [todo for todo in data["todos"] if todo["status"] != "done"]
        recent_activity = data["activity_log"][-10:]
        lines = [
            f"# User Memory: {data['user_id']}",
            "",
            f"- Updated: {data['updated_at']}",
            f"- Total todos: {len(data['todos'])}",
            f"- Open todos: {len(open_todos)}",
            "",
            "## Open Todos",
        ]
        if open_todos:
            for todo in open_todos[:20]:
                lines.append(
                    (
                        f"- [{todo['status']}] {todo['title']} "
                        f"(priority: {todo['priority']}, category: {todo['category']}, "
                        f"id: {todo['id']})"
                    )
                )
        else:
            lines.append("- None")

        lines.extend(["", "## Recent Activity"])
        if recent_activity:
            for event in recent_activity:
                todo_ref = f" todo={event['todo_id']}" if event.get("todo_id") else ""
                lines.append(
                    f"- {event['timestamp']} {event['action']}{todo_ref}: {event['note']}"
                )
        else:
            lines.append("- None")

        lines.extend(
            [
                "",
                "## Canonical Data",
                "",
                "<!-- SODA_DATA_START -->",
                "```json",
                json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
                "```",
                "<!-- SODA_DATA_END -->",
                "",
            ]
        )
        return "\n".join(lines)

    def _empty_document(self, user_id: str) -> dict[str, Any]:
        return {
            "version": 1,
            "user_id": user_id,
            "updated_at": self._now(),
            "todos": [],
            "activity_log": [],
        }

    def _append_activity(
        self,
        data: dict[str, Any],
        action: str,
        note: str,
        todo_id: str | None,
    ) -> None:
        data["activity_log"].append(
            {
                "timestamp": self._now(),
                "action": action,
                "note": note,
                "todo_id": todo_id,
            }
        )

    def _find_todo(self, data: dict[str, Any], todo_id: str) -> dict[str, Any] | None:
        for todo in data["todos"]:
            if todo["id"] == todo_id:
                return todo
        return None

    def _user_path(self, user_id: str) -> Path:
        safe_user_id = re.sub(r"[^A-Za-z0-9._-]", "_", user_id)
        return self._base_dir / f"{safe_user_id}.md"

    def _infer_priority(self, title: str, details: str | None) -> str:
        text = self._normalize_text(f"{title} {details or ''}")
        high_keywords = [
            "urgent",
            "asap",
            "immediately",
            "today",
            "now",
            "critical",
            "긴급",
            "오늘",
            "당장",
            "바로",
        ]
        low_keywords = [
            "later",
            "someday",
            "eventually",
            "maybe",
            "나중",
            "언젠가",
            "여유",
        ]
        if any(keyword in text for keyword in high_keywords):
            return "high"
        if any(keyword in text for keyword in low_keywords):
            return "low"
        return "medium"

    def _infer_category(self, title: str, details: str | None) -> str:
        text = self._normalize_text(f"{title} {details or ''}")
        category_keywords = {
            "work": ["meeting", "client", "project", "deploy", "issue", "업무", "회의", "프로젝트"],
            "personal": ["family", "friend", "birthday", "life", "개인", "가족", "친구"],
            "shopping": ["buy", "purchase", "order", "grocery", "shop", "구매", "장보기", "주문"],
            "health": ["hospital", "clinic", "medicine", "exercise", "건강", "병원", "약", "운동"],
            "finance": ["bill", "invoice", "bank", "tax", "budget", "결제", "세금", "은행"],
            "study": ["study", "learn", "course", "read", "공부", "학습", "강의"],
            "home": ["clean", "repair", "house", "home", "집", "청소", "수리"],
            "travel": ["trip", "flight", "hotel", "travel", "여행", "항공", "숙소"],
            "admin": ["document", "form", "renew", "submit", "서류", "신청", "제출"],
        }
        for category, keywords in category_keywords.items():
            if any(keyword in text for keyword in keywords):
                return category
        return "general"

    def _normalize_status(self, status: str) -> str:
        value = status.strip().lower()
        if value not in VALID_TODO_STATUSES:
            raise ValueError(
                "Invalid status. Use one of: todo, in_progress, review, done."
            )
        return value

    def _normalize_priority(self, priority: str) -> str:
        value = priority.strip().lower()
        if value not in VALID_PRIORITIES:
            raise ValueError("Invalid priority. Use one of: high, medium, low.")
        return value

    def _normalize_category(self, category: str) -> str:
        value = category.strip().lower().replace(" ", "_")
        return re.sub(r"[^a-z0-9_/-]", "", value) or "general"

    def _normalize_text(self, value: str) -> str:
        return value.strip().lower()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()


user_markdown_store = UserMarkdownStore()
