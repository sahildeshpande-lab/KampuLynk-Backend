from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db.db import get_db
from ..models.model import Invitation, InvitationCode, User
from ..models.schemas import ApiResponse, InvitationSendRequest
from ..services import invitation_service
from .shared import api_response, get_current_user

INVITATION_TAG = "5] Invitations"

router = APIRouter(tags=[INVITATION_TAG])


@router.get("/invitations/code", response_model=ApiResponse)
def get_my_invitation_code(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    invite_code = invitation_service.get_or_create_active_code(db, user.id)

    if user.invitation_code != invite_code.code:
        user.invitation_code = invite_code.code
        db.commit()

    return api_response(
        "Invitation code fetched",
        {
            "code": invite_code.code,
            "deepLinkUrl": invitation_service.invitation_deep_link_url(invite_code.code),
            "webUrl": invitation_service.invitation_web_url(invite_code.code),
        },
    )


@router.post("/invitations/send", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def send_invitation(
    payload: InvitationSendRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    invited_email = payload.email.strip().lower()
    if invited_email == user.email.strip().lower():
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": True, "message": "Invitation skipped", "data": {}, "detail": "User cannot invite itself"},
        )

    existing_user = (
        db.query(User)
        .filter(func.lower(func.trim(User.email)) == invited_email)
        .first()
    )
    if existing_user:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": True, "message": "Invitation skipped", "data": {}, "detail": "User already exists"},
        )

    today_count = invitation_service.invitations_sent_today(db, user.id)
    daily_limit = invitation_service.INVITATION_DAILY_LIMIT
    if today_count >= daily_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Invitation limit reached for today ({daily_limit})",
        )

    if invitation_service.email_invited_recently(db, payload.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email was invited recently. Please try again later.",
        )

    invite_code = invitation_service.get_or_create_active_code(db, user.id)
    if user.invitation_code != invite_code.code:
        user.invitation_code = invite_code.code

    invitation = Invitation(
        invitation_code_id=invite_code.id,
        originator_user_id=user.id,
        invited_email=invited_email,
    )
    db.add(invitation)
    db.commit()

    remaining = max(daily_limit - (today_count + 1), 0)
    return api_response(
        "Invitation created",
        {
            "code": invite_code.code,
            "deepLinkUrl": invitation_service.invitation_deep_link_url(invite_code.code),
            "webUrl": invitation_service.invitation_web_url(invite_code.code),
            "remainingToday": remaining,
            "limitPerDay": daily_limit,
        },
    )


@router.get("/invitations/validate/{code}", response_model=ApiResponse)
def validate_invitation_code(code: str, db: Session = Depends(get_db)):
    normalized = code.strip().upper()
    invite_code = (
        db.query(InvitationCode)
        .filter(func.upper(func.trim(InvitationCode.code)) == normalized, InvitationCode.is_active.is_(True))
        .first()
    )
    if not invite_code or not invite_code.originator:
        return api_response("Invalid invitation code", {"isValid": False, "code": normalized})
    return api_response(
        "Invitation code valid",
        {
            "isValid": True,
            "code": invite_code.code,
            "originatorUserId": invite_code.originator.id,
            "originatorName": invite_code.originator.full_name,
        },
    )


@router.get("/invite/{code}", include_in_schema=False)
def invitation_deeplink_redirect(code: str, db: Session = Depends(get_db)):
    normalized = code.strip().upper()
    invite_code = (
        db.query(InvitationCode)
        .filter(func.upper(func.trim(InvitationCode.code)) == normalized, InvitationCode.is_active.is_(True))
        .first()
    )
    if not invite_code:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invitation code")

    deep_link = invitation_service.invitation_deep_link_url(invite_code.code)
    web_url = invitation_service.invitation_web_url(invite_code.code)
    target = deep_link or web_url
    if not target:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invitation deep link is not configured",
        )
    return RedirectResponse(url=target, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
