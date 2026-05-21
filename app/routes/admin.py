from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db.db import get_db
from ..models.model import InvitationCode, User, UserSession
from ..models.schemas import (
    AdminReviewContentActionRequest,
    AdminUserCreate,
    ApiResponse,
    InvitationCodeAdminItem,
    InvitationCodeDeactivateRequest,
    LoginRequest,
    SpamKeywordCreateRequest,
    SpamKeywordUpdateRequest,
    SignupRequest,
    UserUpdate,
)
from ..services import analytics_service
from ..services import post_service
from .shared import (
    _apply_user_update,
    _auth_payload,
    _create_user_from_payload,
    _create_session,
    _get_user_by_email,
    _get_user_or_404,
    _hash_password,
    _password_needs_rehash,
    _user_to_schema,
    _verify_password,
    api_response,
    get_admin_user,
)

ADMIN_TAG = "4] Admin User Management"

router = APIRouter(tags=[ADMIN_TAG])


def _oauth2_token_payload(session: UserSession, user: User) -> dict:
    payload = _auth_payload(session, user)
    return {
        "access_token": payload["accessToken"],
        "token_type": "bearer",
        "refresh_token": payload["refreshToken"],
        "user": payload["user"],
    }


@router.get("/admin/analytics/dau-trend", response_model=ApiResponse)
def admin_dau_trend(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    days: int = Query(default=7, ge=1, le=90),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
):
    data = analytics_service.dau_trend(
        db,
        days=days,
        start_date=start_date,
        end_date=end_date,
    )
    return api_response("DAU trend fetched", data)


@router.get("/admin/analytics/dashboard", response_model=ApiResponse)
def admin_analytics_dashboard(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    days: int = Query(default=7, ge=1, le=90),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    top_limit: int = Query(default=5, ge=1, le=20),
):
    data = analytics_service.dashboard(
        db,
        days=days,
        start_date=start_date,
        end_date=end_date,
        top_limit=top_limit,
    )
    return api_response("Admin analytics dashboard fetched", data)


@router.get("/admin/review/content", response_model=ApiResponse)
def admin_review_queue(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    type: str | None = Query(default=None),
    moderationStatus: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
):
    if type and type not in {"post", "comment", "user"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="type must be post, comment, or user")
    data = post_service.list_moderation_queue(
        db=db,
        content_type=type,
        moderation_status=moderationStatus,
        page=page,
        page_size=pageSize,
    )
    return api_response("Moderation queue fetched", data)


@router.post("/admin/review/content/{contentId}", response_model=ApiResponse)
def admin_review_content_action(
    contentId: str,
    payload: AdminReviewContentActionRequest,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    post_service.review_moderated_content(
        db=db,
        admin_user=admin_user,
        content_id=contentId,
        content_type=payload.type,
        action=payload.action,
        note=payload.note,
    )
    return api_response("Moderation action applied")


@router.get("/admin/spam-words", response_model=ApiResponse)
def admin_list_spam_words(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    type: str | None = Query(default=None),
):
    if type and type not in {"spam", "profanity"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="type must be spam or profanity")
    items = post_service.list_spam_keywords(db=db, keyword_type=type)
    return api_response("Spam keywords fetched" if items else "Data not found", {"items": items})


@router.post("/admin/spam-words", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def admin_create_spam_word(
    payload: SpamKeywordCreateRequest,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    item = post_service.create_spam_keyword(
        db=db,
        admin_user=admin_user,
        keyword=payload.keyword,
        keyword_type=payload.type,
        is_active=payload.isActive,
    )
    return api_response("Spam keyword created", item)


@router.patch("/admin/spam-words/{keywordId}", response_model=ApiResponse)
def admin_update_spam_word(
    keywordId: str,
    payload: SpamKeywordUpdateRequest,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    item = post_service.update_spam_keyword(
        db=db,
        admin_user=admin_user,
        keyword_id=keywordId,
        keyword=payload.keyword,
        keyword_type=payload.type,
        is_active=payload.isActive,
    )
    return api_response("Spam keyword updated", item)


@router.post("/auth/admin/signup", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def admin_signup(payload: SignupRequest, db: Session = Depends(get_db)):
    if _get_user_by_email(db, payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = _create_user_from_payload(payload, role="superadmin")
    user.is_email_verified = True
    db.add(user)
    db.commit()
    db.refresh(user)
    session = _create_session(db, user)
    return api_response("Admin signup successful", _auth_payload(session, user))


@router.post("/auth/admin/signin", response_model=ApiResponse)
def admin_signin(payload: LoginRequest, db: Session = Depends(get_db)):
    user = _get_user_by_email(db, payload.email)
    if not user or not _verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
    if user.role not in {"superadmin", "moderator", "viewer"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    if _password_needs_rehash(user.password_hash):
        user.password_hash = _hash_password(payload.password)
        db.commit()
    session = _create_session(db, user)
    return api_response("Admin signin successful", _auth_payload(session, user))


@router.post("/auth/admin/token")
def admin_login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = _get_user_by_email(db, form_data.username)
    if not user or not _verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
    if user.role not in {"superadmin", "moderator", "viewer"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    if _password_needs_rehash(user.password_hash):
        user.password_hash = _hash_password(form_data.password)
        db.commit()
    session = _create_session(db, user)
    return _oauth2_token_payload(session, user)


@router.get("/users/", response_model=ApiResponse)
def admin_list_users(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=100),
):
    offset = (page - 1) * pageSize
    total = db.query(User).count()
    users = db.query(User).order_by(User.created_at.desc()).offset(offset).limit(pageSize).all()
    if not users:
        return api_response(
            "Data not found",
            {
                "items": [],
                "pagination": {
                    "page": page,
                    "pageSize": pageSize,
                    "totalRecords": total,
                    "totalPages": (total + pageSize - 1) // pageSize if total else 0,
                },
            },
        )
    return api_response(
        "Users fetched",
        {
            "items": [_user_to_schema(user) for user in users],
            "pagination": {
                "page": page,
                "pageSize": pageSize,
                "totalRecords": total,
                "totalPages": (total + pageSize - 1) // pageSize,
            },
        },
    )


@router.post("/users/admin", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def admin_create_user(
    payload: AdminUserCreate,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    if _get_user_by_email(db, payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = _create_user_from_payload(payload, role=payload.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return api_response("User created by admin", _user_to_schema(user))


@router.get("/users/admin/{userId}", response_model=ApiResponse)
def admin_get_user(userId: str, _: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    user = _get_user_or_404(db, userId)
    return api_response("User fetched by admin", _user_to_schema(user))


@router.patch("/users/admin/{userId}", response_model=ApiResponse)
def admin_update_user(
    userId: str,
    payload: UserUpdate,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, userId)
    _apply_user_update(user, payload)
    db.commit()
    db.refresh(user)
    return api_response("User updated by admin", _user_to_schema(user))


@router.delete("/users/admin/{userId}", response_model=ApiResponse)
def admin_delete_user(userId: str, _: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    user = _get_user_or_404(db, userId)
    user.is_active = False
    db.query(UserSession).filter(UserSession.user_id == user.id).update({"is_active": False})
    db.commit()
    return api_response("User deleted by admin")


@router.get("/admin/invitation-codes", response_model=ApiResponse)
def admin_list_invitation_codes(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=100),
    activeOnly: bool = Query(default=False),
):
    offset = (page - 1) * pageSize
    query = db.query(InvitationCode).order_by(InvitationCode.created_at.desc())
    if activeOnly:
        query = query.filter(InvitationCode.is_active.is_(True))
    total = query.count()
    items = query.offset(offset).limit(pageSize).all()
    payload_items = [
        InvitationCodeAdminItem(
            id=item.id,
            code=item.code,
            originatorUserId=item.originator_user_id,
            originatorEmail=item.originator.email if item.originator else None,
            isActive=item.is_active,
            createdAt=item.created_at,
            deactivatedAt=item.deactivated_at,
            deactivatedByUserId=item.deactivated_by_user_id,
            deactivationReason=item.deactivation_reason,
        ).model_dump()
        for item in items
    ]
    return api_response(
        "Invitation codes fetched" if payload_items else "Data not found",
        {
            "items": payload_items,
            "pagination": {
                "page": page,
                "pageSize": pageSize,
                "totalRecords": total,
                "totalPages": (total + pageSize - 1) // pageSize if total else 0,
            },
        },
    )


@router.get("/admin/invitation-codes/{codeId}", response_model=ApiResponse)
def admin_get_invitation_code(codeId: str, _: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    item = db.query(InvitationCode).filter(InvitationCode.id == codeId).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation code not found")
    payload = InvitationCodeAdminItem(
        id=item.id,
        code=item.code,
        originatorUserId=item.originator_user_id,
        originatorEmail=item.originator.email if item.originator else None,
        isActive=item.is_active,
        createdAt=item.created_at,
        deactivatedAt=item.deactivated_at,
        deactivatedByUserId=item.deactivated_by_user_id,
        deactivationReason=item.deactivation_reason,
    ).model_dump()
    return api_response("Invitation code fetched", payload)


@router.patch("/admin/invitation-codes/{codeId}/deactivate", response_model=ApiResponse)
def admin_deactivate_invitation_code(
    codeId: str,
    payload: InvitationCodeDeactivateRequest,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    item = db.query(InvitationCode).filter(InvitationCode.id == codeId).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation code not found")
    if not item.is_active:
        return api_response("Invitation code already inactive")
    item.is_active = False
    item.deactivated_at = func.now()
    item.deactivated_by_user_id = admin.id
    item.deactivation_reason = payload.reason
    db.commit()
    return api_response("Invitation code deactivated")
