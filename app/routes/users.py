from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db.db import get_db
from ..models.model import User, UserNotification, UserSession
from ..models.schemas import ApiResponse, ChangePasswordRequest, ProfileVisibilityUpdate, ReportUserRequest, UserUpdate
from ..services import post_service
from ..services.push_dispatcher import dispatch_queued_push_notifications
from .shared import (
    _apply_user_update,
    _hash_password,
    _is_connected,
    _public_user,
    _user_to_schema,
    _verify_password,
    api_response,
    get_current_user,
    get_current_user_optional,
)

USER_TAG = "2] User Management"

router = APIRouter(tags=[USER_TAG])


def _send_password_changed(email: str, first_name: str | None = None, last_name: str | None = None) -> bool:
    from app import main as main_module
    full_name = f"{first_name} {last_name}" if first_name and last_name else (first_name or last_name or None)
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


@router.patch("/users/me/visibility", response_model=ApiResponse)
def update_visibility(
    payload: ProfileVisibilityUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.profile_visibility = payload.profileVisibility
    db.commit()
    db.refresh(current_user)
    return api_response("Profile visibility updated", {"profileVisibility": current_user.profile_visibility})


@router.post("/users/me/change-password", response_model=ApiResponse)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.login_type != "email" or not _verify_password(payload.currentPassword, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid current password")
    current_user.password_hash = _hash_password(payload.newPassword)
    db.commit()
    sent = _send_password_changed(current_user.email, current_user.first_name, current_user.last_name)
    preferences = current_user.notification_preferences
    allow_in_app = preferences.get("inApp", True) if preferences else True
    allow_push = preferences.get("push", True) if preferences else True
    notification = None
    if allow_in_app or allow_push:
        notification = UserNotification(
            user_id=current_user.id,
            notification_type="password-changed",
            target_type="direct",
            template_key=None,
            title="Password changed",
            body="Your password was changed successfully. If this wasn't you, secure your account immediately.",
            channels={"email": False, "inApp": allow_in_app, "push": allow_push},
            delivery_status={
                "email": "sent" if sent else "failed",
                "inApp": "created" if allow_in_app else "skipped",
                "push": "queued" if allow_push else "skipped",
            },
        )
        db.add(notification)
        db.commit()
    if notification and allow_push:
        db.refresh(notification)
        dispatch_queued_push_notifications(db, [notification.id])
    return api_response("Password changed")


@router.delete("/users/me", response_model=ApiResponse)
def delete_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.is_delete = True
    db.query(UserSession).filter(UserSession.user_id == current_user.id).update({"is_active": False})
    db.commit()
    return api_response("Current user deleted")


@router.get("/users/me/export", response_model=ApiResponse)
def export_me(current_user: User = Depends(get_current_user)):
    return api_response("Current user exported", _user_to_schema(current_user))


@router.get("/users/{userId}", response_model=ApiResponse)
def get_public_user(userId: str, db: Session = Depends(get_db), current_user: User | None = Depends(get_current_user_optional)):
    user = db.query(User).filter(User.id == userId, User.is_delete.is_(False)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.profile_visibility == "connections_only":
        if not current_user or not _is_connected(user, current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Profile is connections only")
    return api_response("Public user fetched", _public_user(user))


@router.post("/users/{userId}/follow", response_model=ApiResponse)
def follow_user(userId: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == userId, User.is_delete.is_(False)).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if userId == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot follow yourself")
    if userId in (current_user.blocked_user_ids or []):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is blocked")
    current_user.following_user_ids = list(dict.fromkeys((current_user.following_user_ids or []) + [userId]))
    db.commit()
    return api_response("User followed", {"userId": userId})


@router.delete("/users/{userId}/follow", response_model=ApiResponse)
def unfollow_user(userId: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.following_user_ids = [i for i in (current_user.following_user_ids or []) if i != userId]
    db.commit()
    return api_response("User unfollowed", {"userId": userId})


@router.post("/users/{userId}/block", response_model=ApiResponse)
def block_user(userId: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == userId, User.is_delete.is_(False)).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if userId == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot block yourself")

    current_user.blocked_user_ids = list(dict.fromkeys((current_user.blocked_user_ids or []) + [userId]))

    current_user.following_user_ids = [i for i in (current_user.following_user_ids or []) if i != userId]
    current_user.connection_request_user_ids = [i for i in (current_user.connection_request_user_ids or []) if i != userId]
    current_user.connected_user_ids = [i for i in (current_user.connected_user_ids or []) if i != userId]

    target.following_user_ids = [i for i in (target.following_user_ids or []) if i != current_user.id]
    target.connection_request_user_ids = [i for i in (target.connection_request_user_ids or []) if i != current_user.id]
    target.connected_user_ids = [i for i in (target.connected_user_ids or []) if i != current_user.id]

    db.commit()
    return api_response("User blocked", {"userId": userId})


@router.delete("/users/{userId}/block", response_model=ApiResponse)
def unblock_user(userId: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.blocked_user_ids = [i for i in (current_user.blocked_user_ids or []) if i != userId]
    db.commit()
    return api_response("User unblocked", {"userId": userId})


@router.patch("/users/{userId}/report", response_model=ApiResponse)
def report_user(
    userId: str,
    payload: ReportUserRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reasons = [payload.reason]
    if payload.description:
        reasons.append(payload.description.strip()[:200])
    post_service.report_user(db, current_user, userId, reasons)
    current_user.reported_user_ids = list(dict.fromkeys((current_user.reported_user_ids or []) + [userId]))
    db.commit()
    return api_response("User reported", {"userId": userId})


@router.post("/users/{userId}/lynkup/request", response_model=ApiResponse)
def lynkup_request(userId: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == userId, User.is_delete.is_(False)).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if userId == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot connect to yourself")
    if userId in (current_user.blocked_user_ids or []) or current_user.id in (target.blocked_user_ids or []):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is blocked")

    if userId in (current_user.connected_user_ids or []):
        return api_response("Already connected", {"userId": userId})

    if userId in (current_user.connection_request_user_ids or []):
        current_user.connection_request_user_ids = [i for i in (current_user.connection_request_user_ids or []) if i != userId]
        target.connection_request_user_ids = [i for i in (target.connection_request_user_ids or []) if i != current_user.id]

        current_user.connected_user_ids = list(dict.fromkeys((current_user.connected_user_ids or []) + [userId]))
        target.connected_user_ids = list(dict.fromkeys((target.connected_user_ids or []) + [current_user.id]))

        current_user.connections_count = len(current_user.connected_user_ids)
        target.connections_count = len(target.connected_user_ids)
        db.commit()
        return api_response("LynkUp connected", {"userId": userId, "status": "connected"})

    target.connection_request_user_ids = list(dict.fromkeys((target.connection_request_user_ids or []) + [current_user.id]))
    db.commit()
    return api_response("LynkUp request sent", {"userId": userId, "status": "requested"})


@router.post("/users/{userId}/lynkup/accept", response_model=ApiResponse)
def lynkup_accept(userId: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == userId, User.is_delete.is_(False)).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if current_user.id in (target.blocked_user_ids or []) or userId in (current_user.blocked_user_ids or []):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is blocked")

    if userId not in (current_user.connection_request_user_ids or []):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No pending request to accept")

    current_user.connection_request_user_ids = [i for i in (current_user.connection_request_user_ids or []) if i != userId]
    target.connection_request_user_ids = [i for i in (target.connection_request_user_ids or []) if i != current_user.id]

    current_user.connected_user_ids = list(dict.fromkeys((current_user.connected_user_ids or []) + [userId]))
    target.connected_user_ids = list(dict.fromkeys((target.connected_user_ids or []) + [current_user.id]))

    current_user.connections_count = len(current_user.connected_user_ids)
    target.connections_count = len(target.connected_user_ids)
    db.commit()
    return api_response("LynkUp connected", {"userId": userId, "status": "connected"})


@router.delete("/users/{userId}/lynkup", response_model=ApiResponse)
def lynkup_remove(userId: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == userId, User.is_delete.is_(False)).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    current_user.connection_request_user_ids = [i for i in (current_user.connection_request_user_ids or []) if i != userId]
    target.connection_request_user_ids = [i for i in (target.connection_request_user_ids or []) if i != current_user.id]

    current_user.connected_user_ids = [i for i in (current_user.connected_user_ids or []) if i != userId]
    target.connected_user_ids = [i for i in (target.connected_user_ids or []) if i != current_user.id]

    current_user.connections_count = len(current_user.connected_user_ids or [])
    target.connections_count = len(target.connected_user_ids or [])

    db.commit()
    return api_response("LynkUp removed", {"userId": userId})
