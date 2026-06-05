from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models.model import UserDevice, UserNotification
from .push_service import PushDeliveryResult, push_service


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _push_status(notification: UserNotification) -> str | None:
    status = (notification.delivery_status or {}).get("push")
    if isinstance(status, dict):
        return status.get("status")
    return status


def _push_payload(notification: UserNotification) -> dict[str, str]:
    payload = {
        "notification_id": notification.id,
        "type": notification.notification_type,
        "action": "open_notification",
        "target_type": notification.target_type,
    }
    if notification.topic:
        payload["topic"] = notification.topic
    if notification.template_key:
        payload["entity_id"] = notification.template_key
        payload["template_key"] = notification.template_key
    return {key: str(value) for key, value in payload.items() if value is not None}


def _set_push_delivery_status(
    notification: UserNotification,
    push_status: str,
    details: dict | None = None,
) -> None:
    delivery_status = dict(notification.delivery_status or {})
    delivery_status["push"] = push_status
    if details is not None:
        delivery_status["pushDetails"] = details
    notification.delivery_status = delivery_status


def dispatch_notification_push(db: Session, notification: UserNotification) -> PushDeliveryResult:
    channels = notification.channels or {}
    if not channels.get("push"):
        _set_push_delivery_status(notification, "skipped", {"reason": "Push channel disabled", "updatedAt": _now_iso()})
        return PushDeliveryResult(status="skipped", failure_reason="Push channel disabled")

    if _push_status(notification) not in {"queued", "sending"}:
        return PushDeliveryResult(status="skipped", failure_reason="Notification is not queued for push")

    devices = db.query(UserDevice).filter(
        UserDevice.user_id == notification.user_id,
        UserDevice.is_active.is_(True),
    ).all()
    tokens = [device.device_token for device in devices]
    if not tokens:
        _set_push_delivery_status(notification, "skipped", {"reason": "No active device tokens", "updatedAt": _now_iso()})
        return PushDeliveryResult(status="skipped", failure_reason="No active device tokens")

    _set_push_delivery_status(notification, "sending", {"startedAt": _now_iso(), "deviceCount": len(tokens)})
    db.flush()

    result = push_service.send_multicast_sync(tokens, notification.title, notification.body, _push_payload(notification))

    if result.invalid_tokens:
        db.query(UserDevice).filter(UserDevice.device_token.in_(result.invalid_tokens)).update(
            {"is_active": False},
            synchronize_session=False,
        )

    details = result.to_dict()
    details["sentAt"] = _now_iso() if result.success_count else None
    details["updatedAt"] = _now_iso()
    _set_push_delivery_status(notification, result.status, details)
    return result


def dispatch_queued_push_notifications(db: Session, notification_ids: list[str] | None = None) -> list[PushDeliveryResult]:
    query = db.query(UserNotification).filter(UserNotification.channels["push"].as_boolean().is_(True))
    if notification_ids:
        query = query.filter(UserNotification.id.in_(notification_ids))

    results: list[PushDeliveryResult] = []
    for notification in query.all():
        if _push_status(notification) == "queued":
            results.append(dispatch_notification_push(db, notification))
    db.commit()
    return results
