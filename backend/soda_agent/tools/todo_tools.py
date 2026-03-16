"""Todo tools backed by the temporary user Markdown store."""

from __future__ import annotations

from services.live_tool_context import get_active_user_id
from services.user_markdown_store import user_markdown_store


def add_todo(
    title: str,
    details: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    cron: str | None = None,
    phone_number: str | None = None,
    voice_message: str | None = None,
    schedule_timezone: str | None = None,
) -> dict:
    """Create a todo for the current user.

    If priority or category are omitted, the server infers them.
    When cron is provided, the todo becomes a scheduled voice todo.
    """
    user_id = get_active_user_id()
    if not user_id:
        return {"status": "error", "message": "Cannot identify user."}

    if not title.strip():
        return {"status": "error", "message": "Todo title cannot be empty."}

    try:
        todo = user_markdown_store.add_todo(
            user_id=user_id,
            title=title,
            details=details,
            priority=priority,
            category=category,
            cron=cron,
            phone_number=phone_number,
            voice_message=voice_message,
            schedule_timezone=schedule_timezone,
        )
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    schedule = todo.get("schedule")
    schedule_message = ""
    if isinstance(schedule, dict):
        schedule_message = (
            f" It will run on cron {schedule['cron']} in timezone {schedule['timezone']}."
        )

    return {
        "status": "success",
        "message": (
            f"Saved todo '{todo['title']}' with priority {todo['priority']} "
            f"in category {todo['category']}.{schedule_message}"
        ),
        "todo": todo,
    }


def list_todos(
    status: str | None = None,
    category: str | None = None,
    priority: str | None = None,
) -> dict:
    """List todos for the current user with optional filters."""
    user_id = get_active_user_id()
    if not user_id:
        return {"status": "error", "message": "Cannot identify user."}

    try:
        todos = user_markdown_store.list_todos(
            user_id=user_id,
            status=status,
            category=category,
            priority=priority,
        )
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    return {
        "status": "success",
        "message": f"Found {len(todos)} todo(s).",
        "todos": todos,
    }


def search_todos(query: str) -> dict:
    """Search todos related to the user's request."""
    user_id = get_active_user_id()
    if not user_id:
        return {"status": "error", "message": "Cannot identify user."}

    if not query.strip():
        return {"status": "error", "message": "Search query cannot be empty."}

    todos = user_markdown_store.search_todos(user_id=user_id, query=query)
    return {
        "status": "success",
        "message": f"Found {len(todos)} matching todo(s).",
        "todos": todos,
    }


def get_todo(todo_id: str) -> dict:
    """Return one todo for the current user."""
    user_id = get_active_user_id()
    if not user_id:
        return {"status": "error", "message": "Cannot identify user."}

    todo = user_markdown_store.get_todo(user_id=user_id, todo_id=todo_id)
    if todo is None:
        return {
            "status": "error",
            "message": f"Todo '{todo_id}' was not found.",
        }
    return {
        "status": "success",
        "message": f"Loaded todo '{todo['title']}'.",
        "todo": todo,
    }


def update_todo_status(todo_id: str, status: str, note: str | None = None) -> dict:
    """Update a todo status.

    Valid statuses: todo, in_progress, review, done.
    """
    user_id = get_active_user_id()
    if not user_id:
        return {"status": "error", "message": "Cannot identify user."}

    try:
        todo = user_markdown_store.update_todo_status(
            user_id=user_id,
            todo_id=todo_id,
            status=status,
            note=note,
        )
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    if todo is None:
        return {
            "status": "error",
            "message": f"Todo '{todo_id}' was not found.",
        }

    return {
        "status": "success",
        "message": f"Updated '{todo['title']}' to status {todo['status']}.",
        "todo": todo,
    }


def get_todo_history(todo_id: str) -> dict:
    """Return history events for a todo."""
    user_id = get_active_user_id()
    if not user_id:
        return {"status": "error", "message": "Cannot identify user."}

    history = user_markdown_store.get_todo_history(user_id=user_id, todo_id=todo_id)
    if history is None:
        return {
            "status": "error",
            "message": f"Todo '{todo_id}' was not found.",
        }

    return {
        "status": "success",
        "message": f"Found {len(history)} history event(s).",
        "history": history,
    }
