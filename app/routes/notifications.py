from datetime import datetime, timezone
from pathlib import Path
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db.db import get_db
from ..models.model import NotificationType, User, UserNotification
from ..models.schemas import ApiResponse, NotificationTypeCreate, SendNotificationRequest
from ..services.email_service import send_notification_email
from ..services.push_dispatcher import dispatch_queued_push_notifications
from .shared import _academic_interests, _notification_preferences, api_response, get_admin_user, get_current_user

NOTIFICATION_TAG = "3] Notifications"

router = APIRouter(tags=[NOTIFICATION_TAG])
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "notifications"


def _notification_to_schema(notification: UserNotification) -> dict:
    return {
        "id": notification.id,
        "userId": notification.user_id,
        "type": notification.notification_type,
        "targetType": notification.target_type,
        "topic": notification.topic,
        "templateKey": notification.template_key,
        "title": notification.title,
        "body": notification.body,
        "channels": notification.channels,
        "deliveryStatus": notification.delivery_status,
        "isRead": notification.is_read,
        "createdAt": notification.created_at,
        "readAt": notification.read_at,
    }


def _notification_type_to_schema(notification_type: NotificationType) -> dict:
    return {
        "id": notification_type.id,
        "type": notification_type.key,
        "name": notification_type.name,
        "description": notification_type.description,
        "isActive": notification_type.is_active,
        "createdAt": notification_type.created_at,
        "updatedAt": notification_type.updated_at,
    }


def _user_matches_topic(user: User, topic: str) -> bool:
    normalized_topic = topic.strip().lower()
    fields = [user.university, user.major, user.minor, user.education_level, user.location]
    interests = [interest.lower() for interest in _academic_interests(user)]
    return normalized_topic in interests or any(
        normalized_topic == str(field).strip().lower() for field in fields if field
    )


def _users_for_notification(db: Session, payload: SendNotificationRequest) -> tuple[list[User], list[str]]:
    if payload.targetType == "broadcast":
        return db.query(User).filter(User.is_active.is_(True)).all(), []

    if payload.targetType == "topic":
        active_users = db.query(User).filter(User.is_active.is_(True)).all()
        return [user for user in active_users if payload.topic and _user_matches_topic(user, payload.topic)], []

    unique_user_ids = list(dict.fromkeys(payload.userIds))
    users = db.query(User).filter(User.id.in_(unique_user_ids), User.is_active.is_(True)).all()
    found_user_ids = {user.id for user in users}
    missing_user_ids = [user_id for user_id in unique_user_ids if user_id not in found_user_ids]
    return users, missing_user_ids


def _safe_template_name(template_name: str) -> str:
    name = template_name.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid templateName format")
    if ".." in name or "/" in name or "\\" in name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid templateName path")
    if not name.endswith(".html"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="templateName must end with .html")
    return name


def _template_name_from_type(notification_type: str) -> str:
    match notification_type.strip().lower():
        case "resend-otp":
            return "notification_resend_otp_email.html"
        case "user-creation":
            return "notification_user_creation_email.html"
        case _:
            slug = re.sub(r"[^a-z0-9]+", "_", notification_type.strip().lower()).strip("_")
            if not slug:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid type value")
            return f"notification_{slug}_email.html"


def _ensure_template_exists(template_name: str, title: str) -> None:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    template_path = TEMPLATE_DIR / template_name
    if template_path.exists():
        return
    content = (
        '<div style="border-left:4px solid {{crimson}};padding-left:16px;">\n'
        f'  <div style="font-size:12px;color:{{{{dark_gray}}}};margin-bottom:8px;">{title}</div>\n'
        "  {{notification_body}}\n"
        "</div>\n"
    )
    template_path.write_text(content, encoding="utf-8")


def _send_user_notification(db: Session, user: User, payload: SendNotificationRequest) -> UserNotification:
    preferences = _notification_preferences(user)
    requested_channels = payload.channels.model_dump()
    effective_channels = {
        "email": requested_channels["email"] and preferences["email"],
        "inApp": requested_channels["inApp"] and preferences["inApp"],
        "push": requested_channels["push"] and preferences["push"],
    }
    delivery_status = {
        "email": "skipped",
        "inApp": "created" if effective_channels["inApp"] else "skipped",
        "push": "queued" if effective_channels["push"] else "skipped",
    }


    match payload.type:
        case "email":
            notification_type = "send"
        case _:
            notification_type = payload.type

    dynamic_type = db.query(NotificationType).filter(
        NotificationType.key == notification_type,
        NotificationType.is_active.is_(True),
    ).first()
    template_name = dynamic_type.template_name if dynamic_type and dynamic_type.template_name else None

    if effective_channels["email"]:
        sent = send_notification_email(
            user.email,
            payload.template.subject,
            payload.template.title,
            payload.template.body,
            payload.template.htmlBody,
            notification_type,
            template_name,
        )
        delivery_status["email"] = "sent" if sent else "failed"

    notification = UserNotification(
        user_id=user.id,
        notification_type=notification_type,
        target_type=payload.targetType,
        topic=payload.topic,
        template_key=payload.template.id,
        title=payload.template.title,
        body=payload.template.body,
        html_body=payload.template.htmlBody,
        channels=effective_channels,
        delivery_status=delivery_status,
    )
    db.add(notification)
    return notification


@router.post("/notifications", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def send_notification(
    payload: SendNotificationRequest,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    users, missing_user_ids = _users_for_notification(db, payload)
    if not users:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active users found")

    notifications = [_send_user_notification(db, user, payload) for user in users]
    db.commit()
    for notification in notifications:
        db.refresh(notification)

    dispatch_queued_push_notifications(db, [notification.id for notification in notifications])
    for notification in notifications:
        db.refresh(notification)

    return api_response(
        "Notification processed",
        {
            "items": [_notification_to_schema(notification) for notification in notifications],
            "summary": {
                "requested": len(payload.userIds) if payload.targetType == "direct" else len(users),
                "processed": len(notifications),
                "type": payload.type,
                "targetType": payload.targetType,
                "topic": payload.topic,
                "missingOrInactiveUserIds": missing_user_ids,
            },
        },
    )


@router.get("/notifications", response_model=ApiResponse)
def get_notifications_by_type(
    type: str = Query(default="send", min_length=1, max_length=80),
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
):
    query = db.query(UserNotification).filter(UserNotification.notification_type == type)
    total = query.count()
    notifications = (
        query.order_by(UserNotification.created_at.desc())
        .offset((page - 1) * pageSize)
        .limit(pageSize)
        .all()
    )
    return api_response(
        "Notifications fetched",
        {
            "items": [_notification_to_schema(notification) for notification in notifications],
            "pagination": {
                "page": page,
                "pageSize": pageSize,
                "totalRecords": total,
                "totalPages": (total + pageSize - 1) // pageSize if total else 0,
            },
        },
    )


@router.post("/notifications/types", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def add_notification_type(
    payload: NotificationTypeCreate,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    existing_type = db.query(NotificationType).filter(NotificationType.key == payload.type).first()
    if existing_type:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Notification type already exists")
    safe_template_name = _safe_template_name(_template_name_from_type(payload.type))
    _ensure_template_exists(safe_template_name, payload.name)

    notification_type = NotificationType(
        key=payload.type,
        name=payload.name,
        description=payload.description,
        template_name=safe_template_name,
        is_active=payload.isActive,
    )
    db.add(notification_type)
    db.commit()
    db.refresh(notification_type)
    return api_response("Notification type created", _notification_type_to_schema(notification_type))


@router.get("/notifications/me", response_model=ApiResponse)
def list_my_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    unreadOnly: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
):
    query = db.query(UserNotification).filter(
        UserNotification.user_id == current_user.id,
        UserNotification.channels["inApp"].as_boolean().is_(True),
    )
    if unreadOnly:
        query = query.filter(UserNotification.is_read.is_(False))

    total = query.count()
    notifications = (
        query.order_by(UserNotification.created_at.desc())
        .offset((page - 1) * pageSize)
        .limit(pageSize)
        .all()
    )

    return api_response(
        "Notifications fetched",
        {
            "items": [_notification_to_schema(notification) for notification in notifications],
            "pagination": {
                "page": page,
                "pageSize": pageSize,
                "totalRecords": total,
                "totalPages": (total + pageSize - 1) // pageSize if total else 0,
            },
        },
    )


@router.patch("/notifications/{notificationId}/read", response_model=ApiResponse)
def mark_notification_read(
    notificationId: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notification = db.query(UserNotification).filter(
        UserNotification.id == notificationId,
        UserNotification.user_id == current_user.id,
    ).first()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(notification)
    return api_response("Notification marked as read", _notification_to_schema(notification))
