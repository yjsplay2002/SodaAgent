from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from services.auth_context import require_authenticated_user
from services.firebase_auth_service import AuthenticatedUser
from services.ws_ticket_store import ws_ticket_store

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthSessionResponse(BaseModel):
    uid: str
    email: str | None = None
    display_name: str | None = None
    photo_url: str | None = None
    ws_ticket: str
    ws_ticket_expires_at: datetime


@router.post("/session", response_model=AuthSessionResponse)
async def create_auth_session(
    user: AuthenticatedUser = Depends(require_authenticated_user),
):
    ticket = ws_ticket_store.issue(user.uid)
    return AuthSessionResponse(
        uid=user.uid,
        email=user.email,
        display_name=user.display_name,
        photo_url=user.photo_url,
        ws_ticket=ticket.token,
        ws_ticket_expires_at=ticket.expires_at,
    )
