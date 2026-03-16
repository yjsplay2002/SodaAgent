"""Firebase Auth helpers for verifying client ID tokens."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import firebase_admin
from firebase_admin import auth, credentials
from firebase_admin.exceptions import FirebaseError

_APP_NAME = "sodaagent-auth"


class FirebaseAuthConfigurationError(RuntimeError):
    """Raised when the backend cannot initialize Firebase Admin SDK."""


class FirebaseIdTokenError(RuntimeError):
    """Raised when a Firebase ID token is missing or invalid."""


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    uid: str
    email: str | None = None
    display_name: str | None = None
    photo_url: str | None = None


class FirebaseAuthService:
    def verify_id_token(self, id_token: str) -> AuthenticatedUser:
        if not id_token or not id_token.strip():
            raise FirebaseIdTokenError("Missing Firebase ID token.")

        app = self._get_app()
        try:
            decoded = auth.verify_id_token(
                id_token.strip(),
                app=app,
                check_revoked=False,
            )
        except auth.ExpiredIdTokenError as exc:
            raise FirebaseIdTokenError("Firebase ID token has expired.") from exc
        except auth.RevokedIdTokenError as exc:
            raise FirebaseIdTokenError("Firebase ID token has been revoked.") from exc
        except auth.InvalidIdTokenError as exc:
            raise FirebaseIdTokenError("Firebase ID token is invalid.") from exc
        except auth.CertificateFetchError as exc:
            raise FirebaseIdTokenError(
                "Unable to verify the Firebase ID token right now."
            ) from exc
        except FirebaseError as exc:
            raise FirebaseIdTokenError(
                f"Firebase ID token verification failed: {exc}"
            ) from exc

        uid = decoded.get("uid") or decoded.get("sub")
        if not uid:
            raise FirebaseIdTokenError(
                "Firebase ID token did not include a user identifier."
            )

        return AuthenticatedUser(
            uid=str(uid),
            email=_string_or_none(decoded.get("email")),
            display_name=_string_or_none(decoded.get("name")),
            photo_url=_string_or_none(decoded.get("picture")),
        )

    def _get_app(self):
        try:
            return firebase_admin.get_app(_APP_NAME)
        except ValueError:
            pass

        options = self._build_options()
        try:
            service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
            if service_account_json:
                parsed = json.loads(service_account_json)
                credential = credentials.Certificate(parsed)
                return firebase_admin.initialize_app(
                    credential,
                    options=options,
                    name=_APP_NAME,
                )

            return firebase_admin.initialize_app(
                options=options,
                name=_APP_NAME,
            )
        except (ValueError, FirebaseError, TypeError, json.JSONDecodeError) as exc:
            raise FirebaseAuthConfigurationError(
                "Firebase Admin SDK is not configured. "
                "Set FIREBASE_SERVICE_ACCOUNT_JSON or provide application "
                "default credentials before using authenticated routes."
            ) from exc

    def _build_options(self) -> dict[str, str] | None:
        options: dict[str, str] = {}
        project_id = (
            os.getenv("FIREBASE_PROJECT_ID")
            or os.getenv("GOOGLE_CLOUD_PROJECT")
            or os.getenv("GCLOUD_PROJECT")
        )
        storage_bucket = os.getenv("FIREBASE_STORAGE_BUCKET")
        if project_id:
            options["projectId"] = project_id
        if storage_bucket:
            options["storageBucket"] = storage_bucket
        return options or None


def _string_or_none(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


firebase_auth_service = FirebaseAuthService()
