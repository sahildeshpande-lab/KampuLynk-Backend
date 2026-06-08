from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from .db.db import engine, ensure_platform_defaults, migrate_legacy_users_table
from .models.model import Base
from .routes.admin import router as admin_router
from .routes.auth import router as auth_router
from .routes.devices import router as device_router
from .routes.notifications import router as notification_router
from .routes.invitations import router as invitation_router
from .routes.discovery import router as discovery_router
from .routes.posts import POST_TAG, router as post_router
from .routes.users import router as user_router
from .services.email_service import (
    send_account_created_email,
    send_notification_email,
    send_otp_email,
    send_password_changed_email,
)

migrate_legacy_users_table()
Base.metadata.create_all(bind=engine)
ensure_platform_defaults()

AUTH_TAG = "1] Authentication"
USER_TAG = "2] User Management"
NOTIFICATION_TAG = "3] Notifications"
ADMIN_TAG = "4] Admin User Management"
INVITATION_TAG = "5] Invitations"
DISCOVERY_TAG = "6] Search & Discovery"

app = FastAPI(
    title="KampuLynk User Management API",
    version="1.0.0",
    openapi_tags=[
        {
            "name": AUTH_TAG,
            "description": "Signup, verification, social login, session refresh, and logout.",
        },
        {
            "name": USER_TAG,
            "description": "Authenticated user profile, password, export, delete, and public profile APIs.",
        },
        {
            "name": NOTIFICATION_TAG,
            "description": "Admin notification sending and authenticated user in-app notification APIs.",
        },
        {
            "name": ADMIN_TAG,
            "description": "Admin-only authentication and user management APIs.",
        },
        {
            "name": INVITATION_TAG,
            "description": "Invitation code validation, deep links, and invitation sending.",
        },
        {
            "name": DISCOVERY_TAG,
            "description": "Search & discovery APIs (search by name/keyword/hashtag, filter by university/interest, etc.).",
        },
        {
            "name": POST_TAG,
            "description": "Posts, feed pagination, drafts, media metadata, comments, reactions, and repost APIs.",
        },
    ],
)

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(device_router)
app.include_router(admin_router)
app.include_router(notification_router)
app.include_router(invitation_router)
app.include_router(discovery_router)
app.include_router(post_router)


@app.get("/")
def read_root():
    return {"status": True, "message": "KampuLynk User Management API is running", "data": None}


@app.exception_handler(HTTPException)
def http_exception_handler(_, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": False, "message": str(exc.detail), "data": None},
    )


@app.exception_handler(RequestValidationError)
def validation_exception_handler(_, exc: RequestValidationError):
    payload = {"status": False, "message": "Validation error", "data": {"errors": exc.errors()}}
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder(payload),
    )
