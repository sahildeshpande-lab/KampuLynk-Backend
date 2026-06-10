from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..db.db import get_db
from ..models.model import UserSession
from ..models.schemas import (
    ApiResponse,
    ForgotPasswordRequest,
    LoginRequest,
    OAuthRequest,
    RefreshRequest,
    ResendOTPRequest,
    ResetPasswordRequest,
    SignupRequest,
    VerifyOTPRequest,
)
from ..services import auth as auth_service
from .shared import _current_session, api_response

AUTH_TAG = "1] Authentication"

router = APIRouter(tags=[AUTH_TAG])


@router.post("/auth/signup", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    return api_response("Signup successful", auth_service.signup_user(db, payload))


@router.post("/auth/verify-otp", response_model=ApiResponse)
def verify_otp(payload: VerifyOTPRequest, db: Session = Depends(get_db)):
    return api_response("Email verified", auth_service.verify_user_otp(db, payload))


@router.post("/auth/resend-otp", response_model=ApiResponse)
def resend_otp(payload: ResendOTPRequest, db: Session = Depends(get_db)):
    res = auth_service.resend_user_otp(db, payload)
    msg = res.pop("message", "OTP sent")
    return api_response(msg, res)


@router.post("/auth/forgot-password", response_model=ApiResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    res = auth_service.forgot_user_password(db, payload)
    msg = res.pop("message", "OTP as been send to the requested email ID")
    return api_response(msg, res)


@router.post("/auth/reset-password", response_model=ApiResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    return api_response("Password reset successful", auth_service.reset_user_password(db, payload))


@router.post("/auth/login", response_model=ApiResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    return api_response("Login successful", auth_service.login_user(db, payload, request))


@router.post("/auth/token")
def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    return auth_service.login_for_access_token(db, form_data.username, form_data.password, request)


@router.post("/auth/social", response_model=ApiResponse)
def social_login(payload: OAuthRequest, db: Session = Depends(get_db)):
    data = auth_service.social_login_user(db, payload)
    return api_response(f"{payload.provider.title()} login successful", data)


@router.post("/auth/refresh", response_model=ApiResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    return api_response("Token refreshed", auth_service.refresh_auth_session(db, payload))


@router.post("/auth/logout", response_model=ApiResponse)
def logout(session: UserSession = Depends(_current_session), db: Session = Depends(get_db)):
    auth_service.logout_session(db, session)
    return api_response("Logged out")
