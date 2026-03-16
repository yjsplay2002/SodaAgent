from fastapi import APIRouter, HTTPException

from services.conversation_store import conversation_store

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("/{user_id}")
async def list_sessions(user_id: str):
    return {
        "user_id": user_id,
        "sessions": conversation_store.list_conversations(user_id),
    }


@router.get("/{user_id}/{conversation_id}")
async def get_session(user_id: str, conversation_id: str):
    detail = conversation_store.get_conversation(user_id, conversation_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return detail
