import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import firebase_admin
from firebase_admin import credentials, exceptions, messaging

from ..config import load_env_files

logger = logging.getLogger(__name__)


@dataclass
class PushTokenResult:
    token: str
    success: bool
    message_id: str | None = None
    error: str | None = None
    invalid_token: bool = False


@dataclass
class PushDeliveryResult:
    status: str
    success_count: int = 0
    failure_count: int = 0
    provider_message_ids: list[str] = field(default_factory=list)
    invalid_tokens: list[str] = field(default_factory=list)
    failure_reason: str | None = None
    responses: list[PushTokenResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "successCount": self.success_count,
            "failureCount": self.failure_count,
            "providerMessageIds": self.provider_message_ids,
            "invalidTokens": self.invalid_tokens,
            "failureReason": self.failure_reason,
            "responses": [
                {
                    "token": response.token,
                    "success": response.success,
                    "messageId": response.message_id,
                    "error": response.error,
                    "invalidToken": response.invalid_token,
                }
                for response in self.responses
            ],
        }


class PushService:
    def __init__(self) -> None:
        load_env_files()
        self._app: firebase_admin.App | None = None

    def _credential_path(self) -> Path | None:
        configured_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
        if configured_path:
            path = Path(configured_path).expanduser()
            if path.exists():
                return path
            logger.warning("Configured FIREBASE_SERVICE_ACCOUNT_PATH does not exist: %s", path)

        backend_dir = Path(__file__).resolve().parents[2]
        candidates = [
            *(backend_dir / "secrets").glob("*firebase-adminsdk*.json"),
            *(backend_dir / "secrets").glob("*.json"),
            *backend_dir.glob("*firebase-adminsdk*.json"),
        ]
        return sorted(candidates)[0] if candidates else None

    def _firebase_app(self) -> firebase_admin.App | None:
        if self._app:
            return self._app
        if firebase_admin._apps:
            self._app = firebase_admin.get_app()
            return self._app

        credential_path = self._credential_path()
        if not credential_path:
            logger.warning("Firebase service account JSON was not found; push delivery is disabled")
            return None

        try:
            cred = credentials.Certificate(str(credential_path))
            self._app = firebase_admin.initialize_app(cred)
            return self._app
        except Exception:
            logger.exception("Failed to initialize Firebase Admin SDK")
            return None

    @staticmethod
    def _is_invalid_token_error(error: Exception | None) -> bool:
        if error is None:
            return False
        return isinstance(
            error,
            (
                messaging.UnregisteredError,
                messaging.SenderIdMismatchError,
            ),
        ) or (
            isinstance(error, exceptions.InvalidArgumentError)
            and "registration token" in str(error).lower()
        )

    def send_sync(
        self,
        token: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> PushDeliveryResult:
        return self.send_multicast_sync([token], title, body, data)

    def send_multicast_sync(
        self,
        tokens: list[str],
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> PushDeliveryResult:
        unique_tokens = list(dict.fromkeys(token.strip() for token in tokens if token and token.strip()))
        if not unique_tokens:
            return PushDeliveryResult(status="skipped", failure_reason="No active device tokens")

        app = self._firebase_app()
        if not app:
            return PushDeliveryResult(status="failed", failure_count=len(unique_tokens), failure_reason="Firebase is not configured")

        message = messaging.MulticastMessage(
            tokens=unique_tokens,
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
        )
        try:
            batch = messaging.send_each_for_multicast(message, app=app)
        except Exception as exc:
            logger.exception("Firebase push multicast failed")
            invalid = unique_tokens if self._is_invalid_token_error(exc) else []
            return PushDeliveryResult(
                status="failed",
                failure_count=len(unique_tokens),
                failure_reason=str(exc),
                invalid_tokens=invalid,
            )

        responses: list[PushTokenResult] = []
        invalid_tokens: list[str] = []
        message_ids: list[str] = []
        for token, response in zip(unique_tokens, batch.responses, strict=False):
            invalid = self._is_invalid_token_error(response.exception)
            if invalid:
                invalid_tokens.append(token)
            if response.message_id:
                message_ids.append(response.message_id)
            responses.append(
                PushTokenResult(
                    token=token,
                    success=response.success,
                    message_id=response.message_id,
                    error=str(response.exception) if response.exception else None,
                    invalid_token=invalid,
                )
            )

        if batch.success_count == len(unique_tokens):
            status = "sent"
        elif batch.success_count > 0:
            status = "partial"
        else:
            status = "failed"

        return PushDeliveryResult(
            status=status,
            success_count=batch.success_count,
            failure_count=batch.failure_count,
            provider_message_ids=message_ids,
            invalid_tokens=invalid_tokens,
            responses=responses,
        )

    async def send(
        self,
        token: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> PushDeliveryResult:
        return await asyncio.to_thread(self.send_sync, token, title, body, data)

    async def send_multicast(
        self,
        tokens: list[str],
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> PushDeliveryResult:
        return await asyncio.to_thread(self.send_multicast_sync, tokens, title, body, data)


push_service = PushService()
