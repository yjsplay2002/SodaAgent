"""User profile storage backed by Firestore with a local file fallback."""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

try:
    from google.cloud import firestore
except ModuleNotFoundError:
    firestore = None

logger = logging.getLogger(__name__)


class UserIdentity(Protocol):
    uid: str
    email: str | None
    display_name: str | None
    photo_url: str | None


@dataclass(slots=True)
class UserProfile:
    uid: str
    email: str | None = None
    display_name: str | None = None
    photo_url: str | None = None
    phone_number: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


class UserProfileService:
    """Stores user profile metadata for Twilio and future user settings."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        root = (
            Path(base_dir)
            if base_dir is not None
            else Path(__file__).resolve().parent.parent / "data" / "user_profiles"
        )
        self._base_dir = root
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._firestore_client = None
        self._firestore_init_failed = False

    def get_or_create_profile(self, user: UserIdentity) -> UserProfile:
        profile = self.get_profile(user.uid)
        now = self._now()
        if profile is None:
            profile = UserProfile(
                uid=user.uid,
                email=self._string_or_none(user.email),
                display_name=self._string_or_none(user.display_name),
                photo_url=self._string_or_none(user.photo_url),
                created_at=now,
                updated_at=now,
            )
            self._write_profile(profile)
            return profile

        changed = False
        for field_name, value in (
            ("email", self._string_or_none(user.email)),
            ("display_name", self._string_or_none(user.display_name)),
            ("photo_url", self._string_or_none(user.photo_url)),
        ):
            if value and getattr(profile, field_name) != value:
                setattr(profile, field_name, value)
                changed = True

        if changed:
            profile.updated_at = now
            self._write_profile(profile)
        return profile

    def get_profile(self, uid: str) -> UserProfile | None:
        firestore_profile = self._read_from_firestore(uid)
        if firestore_profile is not None:
            return firestore_profile
        return self._read_from_file(uid)

    def get_phone_number(self, uid: str) -> str | None:
        profile = self.get_profile(uid)
        if profile is None:
            return None
        return profile.phone_number

    def update_phone_number(
        self,
        user: UserIdentity,
        phone_number: str | None,
    ) -> UserProfile:
        profile = self.get_or_create_profile(user)
        normalized_phone = self._normalize_phone_number(phone_number)
        profile.phone_number = normalized_phone
        profile.updated_at = self._now()
        self._write_profile(profile)
        return profile

    def _read_from_firestore(self, uid: str) -> UserProfile | None:
        client = self._get_firestore_client()
        if client is None:
            return None

        try:
            snapshot = client.collection("users").document(uid).get()
        except Exception as exc:
            logger.warning("Firestore profile read failed for %s: %s", uid, exc)
            return None

        if not snapshot.exists:
            return None

        data = snapshot.to_dict() or {}
        data["uid"] = uid
        return self._profile_from_dict(data)

    def _write_profile(self, profile: UserProfile) -> None:
        if not self._write_to_firestore(profile):
            self._write_to_file(profile)

    def _write_to_firestore(self, profile: UserProfile) -> bool:
        client = self._get_firestore_client()
        if client is None:
            return False

        try:
            client.collection("users").document(profile.uid).set(
                profile.to_dict(),
                merge=True,
            )
            return True
        except Exception as exc:
            logger.warning("Firestore profile write failed for %s: %s", profile.uid, exc)
            return False

    def _read_from_file(self, uid: str) -> UserProfile | None:
        path = self._profile_path(uid)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        data["uid"] = uid
        return self._profile_from_dict(data)

    def _write_to_file(self, profile: UserProfile) -> None:
        path = self._profile_path(profile.uid)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(profile.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _get_firestore_client(self):
        if self._firestore_init_failed or firestore is None:
            return None
        if self._firestore_client is not None:
            return self._firestore_client

        project_id = (
            os.getenv("FIREBASE_PROJECT_ID")
            or os.getenv("GOOGLE_CLOUD_PROJECT")
            or os.getenv("GCLOUD_PROJECT")
        )
        try:
            kwargs = {"project": project_id} if project_id else {}
            self._firestore_client = firestore.Client(**kwargs)
        except Exception as exc:
            logger.warning("Firestore client unavailable: %s", exc)
            self._firestore_init_failed = True
            return None
        return self._firestore_client

    def _profile_path(self, uid: str) -> Path:
        safe_uid = re.sub(r"[^A-Za-z0-9._-]", "_", uid)
        return self._base_dir / f"{safe_uid}.json"

    def _profile_from_dict(self, data: dict) -> UserProfile:
        return UserProfile(
            uid=str(data.get("uid", "")).strip(),
            email=self._string_or_none(data.get("email")),
            display_name=self._string_or_none(data.get("display_name")),
            photo_url=self._string_or_none(data.get("photo_url")),
            phone_number=self._string_or_none(data.get("phone_number")),
            created_at=self._string_or_none(data.get("created_at")),
            updated_at=self._string_or_none(data.get("updated_at")),
        )

    def _normalize_phone_number(self, value: str | None) -> str | None:
        raw = (value or "").strip()
        if not raw:
            return None

        normalized = re.sub(r"[\s().-]", "", raw)
        if normalized.startswith("00"):
            normalized = f"+{normalized[2:]}"

        if not normalized.startswith("+"):
            raise ValueError(
                "Phone number must include a country code, for example +821012345678."
            )

        digits = normalized[1:]
        if not digits.isdigit() or not 8 <= len(digits) <= 15:
            raise ValueError(
                "Phone number must be in international format, for example +821012345678."
            )

        return f"+{digits}"

    def _string_or_none(self, value: object) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()


user_profile_service = UserProfileService()
