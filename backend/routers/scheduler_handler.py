"""Pub/Sub push endpoint for Cloud Scheduler triggers."""

from fastapi import APIRouter

from services.trigger_engine import TriggerEngine
from services.user_markdown_store import user_markdown_store

router = APIRouter(prefix="/api/triggers", tags=["triggers"])

trigger_engine = TriggerEngine()


@router.post("/evaluate")
async def evaluate_triggers():
    """Evaluate scheduled todo triggers across all stored users."""
    fired_triggers = await trigger_engine.evaluate_triggers()
    active_users = user_markdown_store.list_user_ids()

    return {
        "status": "success",
        "users_evaluated": len(active_users),
        "triggers_fired": len(fired_triggers),
        "details": fired_triggers,
    }
