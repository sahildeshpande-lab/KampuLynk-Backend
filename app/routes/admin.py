from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db.db import get_db
from ..models.model import User, UserSession
from ..models.schemas import AdminUserCreate, ApiResponse, LoginRequest, SignupRequest, UserUpdate
from .shared import (
    _apply_user_update,
    _auth_payload,
    _create_user_from_payload,
    _create_session,
    _get_user_by_email,
    _get_user_or_404,
    _hash_password,
    _user_to_schema,
    api_response,
    get_admin_user,
)

ADMIN_TAG = "4] Admin User Management"

router = APIRouter(tags=[ADMIN_TAG])


@router.post("/auth/admin/signup", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def admin_signup(payload: SignupRequest, db: Session = Depends(get_db)):
    if _get_user_by_email(db, payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = _create_user_from_payload(payload, role="admin")
    user.is_email_verified = True
    db.add(user)
    db.commit()
    db.refresh(user)
    session = _create_session(db, user)
    return api_response("Admin signup successful", _auth_payload(session, user))


@router.post("/auth/admin/signin", response_model=ApiResponse)
def admin_signin(payload: LoginRequest, db: Session = Depends(get_db)):
    user = _get_user_by_email(db, payload.email)
    if not user or user.password_hash != _hash_password(payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    session = _create_session(db, user)
    return api_response("Admin signin successful", _auth_payload(session, user))


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
