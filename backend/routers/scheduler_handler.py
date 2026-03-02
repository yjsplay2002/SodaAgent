"""Pub/Sub push endpoint for Cloud Scheduler triggers."""

from fastapi import APIRouter

from services.trigger_engine import TriggerEngine

router = APIRouter(prefix="/api/triggers", tags=["triggers"])

trigger_engine = TriggerEngine()


@router.post("/evaluate")
async def evaluate_triggers():
    """Evaluate all user triggers. Called by Cloud Scheduler via Pub/Sub.

    Checks each active user's triggers and initiates outbound calls
    when conditions are met.
    """
    # TODO: Fetch active users from Firestore
    # MVP: Use a hardcoded test user
    test_user_id = "test-user-001"

    fired_triggers = trigger_engine.evaluate_triggers(test_user_id)

    # TODO: For each fired trigger, call trigger_engine.fire_trigger()
    # with the user's phone number from Firestore

    return {
        "status": "success",
        "user_id": test_user_id,
        "triggers_evaluated": 1,
        "triggers_fired": len(fired_triggers),
        "details": fired_triggers,
    }
