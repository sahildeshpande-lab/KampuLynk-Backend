from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models.model import User, UserActivity

TRACKED_ACTIVITY_TYPES = {
    "login",
    "app_open",
    "feed_open",
    "post_created",
    "comment_created",
    "message_sent",
}


def track_user_activity(
    db: Session,
    user: User,
    activity_type: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    if activity_type not in TRACKED_ACTIVITY_TYPES:
        return
    db.add(
        UserActivity(
            user_id=user.id,
            activity_type=activity_type,
            activity_metadata=metadata or {},
        )
    )
    db.commit()
