from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services.auth_context import require_authenticated_user
from services.firebase_auth_service import AuthenticatedUser
from services.user_profile_service import user_profile_service
from services.ws_ticket_store import ws_ticket_store

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthSessionResponse(BaseModel):
    uid: str
    email: str | None = None
    display_name: str | None = None
    photo_url: str | None = None
    phone_number: str | None = None
    ws_ticket: str
    ws_ticket_expires_at: datetime


class UserProfileResponse(BaseModel):
    uid: str
    email: str | None = None
    display_name: str | None = None
    photo_url: str | None = None
    phone_number: str | None = None


class UpdateUserProfileRequest(BaseModel):
    phone_number: str | None = None


@router.post("/session", response_model=AuthSessionResponse)
async def create_auth_session(
    user: AuthenticatedUser = Depends(require_authenticated_user),
):
    profile = user_profile_service.get_or_create_profile(user)
    ticket = ws_ticket_store.issue(user.uid)
    return AuthSessionResponse(
        uid=user.uid,
        email=user.email,
        display_name=user.display_name,
        photo_url=user.photo_url,
        phone_number=profile.phone_number,
        ws_ticket=ticket.token,
        ws_ticket_expires_at=ticket.expires_at,
    )


@router.get("/profile", response_model=UserProfileResponse)
async def get_user_profile(
    user: AuthenticatedUser = Depends(require_authenticated_user),
):
    profile = user_profile_service.get_or_create_profile(user)
    return UserProfileResponse(
        uid=profile.uid,
        email=profile.email,
        display_name=profile.display_name,
        photo_url=profile.photo_url,
        phone_number=profile.phone_number,
    )


@router.patch("/profile", response_model=UserProfileResponse)
async def update_user_profile(
    payload: UpdateUserProfileRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
):
    try:
        profile = user_profile_service.update_phone_number(user, payload.phone_number)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return UserProfileResponse(
        uid=profile.uid,
        email=profile.email,
        display_name=profile.display_name,
        photo_url=profile.photo_url,
        phone_number=profile.phone_number,
    )
