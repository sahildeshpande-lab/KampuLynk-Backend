from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from ..db.db import get_db
from ..models.model import User, UserSession
from ..services import auth as auth_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


def api_response(message: str, data=None, ok: bool = True) -> dict:
    return {"status": ok, "message": message, "data": data}


def get_current_user_optional(
    access_token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    return auth_service.current_user_from_token(db, access_token)


def _current_session(
    access_token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> UserSession:
    return auth_service.current_session_from_token(db, access_token)


def get_current_user(session: UserSession = Depends(_current_session)) -> User:
    return session.user


def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if user.role not in {"superadmin", "moderator", "viewer"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


_academic_interests = auth_service.academic_interests
_apply_user_update = auth_service.apply_user_update
_auth_payload = auth_service.auth_payload
_calculate_completeness = auth_service.calculate_completeness
_create_otp = auth_service.create_otp
_create_session = auth_service.create_session
_create_user_from_payload = auth_service.create_user_from_payload
_credentials_exception = auth_service.credentials_exception
_get_user_by_email = auth_service.get_user_by_email
_get_user_or_404 = auth_service.get_user_or_404
_hash_password = auth_service.hash_password
_is_connected = auth_service.is_connected
_jwt_decode = auth_service.jwt_decode
_jwt_encode = auth_service.jwt_encode
_jwt_algorithm = auth_service.jwt_algorithm
_jwt_expire_minutes = auth_service.jwt_expire_minutes
_jwt_secret = auth_service.jwt_secret
_notification_preferences = auth_service.notification_preferences
_otp_not_expired = auth_service.otp_not_expired
_password_needs_rehash = auth_service.password_needs_rehash
_payload_dict = auth_service.payload_dict
_public_user = auth_service.public_user
_token = auth_service.token
_user_to_schema = auth_service.user_to_schema
_verify_password = auth_service.verify_password
