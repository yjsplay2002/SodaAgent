from fastapi import APIRouter, Depends, HTTPException

from services.auth_context import require_authenticated_user
from services.conversation_store import conversation_store
from services.firebase_auth_service import AuthenticatedUser

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("")
async def list_sessions(
    user: AuthenticatedUser = Depends(require_authenticated_user),
):
    return {
        "user_id": user.uid,
        "sessions": conversation_store.list_conversations(user.uid),
    }


@router.get("/{conversation_id}")
async def get_session(
    conversation_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
):
    detail = conversation_store.get_conversation(user.uid, conversation_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return detail
