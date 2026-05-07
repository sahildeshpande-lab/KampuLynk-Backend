from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db.db import get_db
from ..models.model import User, UserSession
from ..models.schemas import ApiResponse, ChangePasswordRequest, UserUpdate
from .shared import (
    _apply_user_update,
    _hash_password,
    _public_user,
    _user_to_schema,
    api_response,
    get_current_user,
)

USER_TAG = "2] User Management"

router = APIRouter(tags=[USER_TAG])


def _send_password_changed(email: str, full_name: str | None = None) -> bool:
    from app import main as main_module
    return main_module.send_password_changed_email(email, full_name)


@router.get("/users/me", response_model=ApiResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return api_response("Current user fetched", _user_to_schema(current_user))


@router.patch("/users/me", response_model=ApiResponse)
def update_me(payload: UserUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _apply_user_update(current_user, payload)
    db.commit()
    db.refresh(current_user)
    return api_response("Current user updated", _user_to_schema(current_user))


@router.post("/users/me/change-password", response_model=ApiResponse)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.login_type != "email" or current_user.password_hash != _hash_password(payload.currentPassword):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid current password")
    current_user.password_hash = _hash_password(payload.newPassword)
    db.commit()
    _send_password_changed(current_user.email, current_user.full_name)
    return api_response("Password changed")


@router.delete("/users/me", response_model=ApiResponse)
def delete_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.is_active = False
    db.query(UserSession).filter(UserSession.user_id == current_user.id).update({"is_active": False})
    db.commit()
    return api_response("Current user deleted")


@router.get("/users/me/export", response_model=ApiResponse)
def export_me(current_user: User = Depends(get_current_user)):
    return api_response("Current user exported", _user_to_schema(current_user))


@router.get("/users/{userId}", response_model=ApiResponse)
def get_public_user(userId: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == userId, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return api_response("Public user fetched", _public_user(user))
