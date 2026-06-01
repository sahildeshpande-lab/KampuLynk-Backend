import os
import secrets
import string
from datetime import datetime, timedelta, timezone , UTC
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.model import Invitation, InvitationCode


INVITATION_DAILY_LIMIT = int(os.getenv("INVITATION_DAILY_LIMIT", "50"))
INVITATION_TIMEZONE = os.getenv("INVITATION_TIMEZONE", "Asia/Calcutta")
INVITATION_BLOCK_EMAIL_DAYS = int(os.getenv("INVITATION_BLOCK_EMAIL_DAYS", "7"))
INVITATION_CODE_LENGTH = int(os.getenv("INVITATION_CODE_LENGTH", "10"))


def invitation_deep_link_url(code: str) -> str | None:
    base = os.getenv("INVITATION_DEEP_LINK_BASE")
    if not base:
        return None
    base = base.rstrip("/")
    if "?" in base:
        return f"{base}&code={code}"
    return f"{base}?code={code}"


def invitation_web_url(code: str) -> str | None:
    base = os.getenv("INVITATION_WEB_URL_BASE")
    if not base:
        return None
    base = base.rstrip("/")
    return f"{base}/{code}"


def _alphabet() -> str:
    return "".join(ch for ch in (string.ascii_uppercase + string.digits) if ch not in {"0", "O", "1", "I"})


def generate_invitation_code() -> str:
    alphabet = _alphabet()
    return "".join(secrets.choice(alphabet) for _ in range(INVITATION_CODE_LENGTH))


def get_or_create_active_code(db: Session, originator_user_id: str) -> InvitationCode:
    existing = (
        db.query(InvitationCode)
        .filter(InvitationCode.originator_user_id == originator_user_id, InvitationCode.is_active.is_(True))
        .order_by(InvitationCode.created_at.desc())
        .first()
    )
    if existing:
        return existing

    for _ in range(10):
        code = generate_invitation_code()
        if not db.query(InvitationCode).filter(InvitationCode.code == code).first():
            invite_code = InvitationCode(code=code, originator_user_id=originator_user_id, is_active=True)
            db.add(invite_code)
            db.commit()
            db.refresh(invite_code)
            return invite_code

    raise ValueError("Could not generate a unique invitation code")


def utc_day_bounds_for_timezone(now_utc: datetime | None = None) -> tuple[datetime, datetime]:
    now_utc = now_utc or datetime.now(timezone.utc)
    try:
        tz = ZoneInfo(INVITATION_TIMEZONE)
    except Exception:
        if INVITATION_TIMEZONE in {"Asia/Calcutta", "Asia/Kolkata", "IST"}:
            tz = timezone(timedelta(hours=5, minutes=30))
        else:
            tz = timezone.utc
    local = now_utc.astimezone(tz)
    local_start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    local_end = local_start + timedelta(days=1)
    start_utc = local_start.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = local_end.astimezone(timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc


def invitations_sent_today(db: Session, originator_user_id: str) -> int:
    start_utc, end_utc = utc_day_bounds_for_timezone()
    return (
        db.query(Invitation)
        .filter(
            Invitation.originator_user_id == originator_user_id,
            Invitation.created_at >= start_utc,
            Invitation.created_at < end_utc,
        )
        .count()
    )


def email_invited_recently(db: Session, email: str) -> bool:
    normalized = email.strip().lower()
    cutoff = (datetime.now(UTC)  - timedelta(days=INVITATION_BLOCK_EMAIL_DAYS))
    
    return (
        db.query(Invitation)
        .filter(func.lower(func.trim(Invitation.invited_email)) == normalized, Invitation.created_at >= cutoff)
        .first()
        is not None
    )
