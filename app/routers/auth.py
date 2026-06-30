from fastapi import APIRouter, Depends, BackgroundTasks, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.schemas import (
    RegisterRequest, OTPVerifyRequest, LoginRequest, LoginOTPVerifyRequest,
    ForgotPasswordRequest, ResetPasswordRequest,
    RefreshRequest, LogoutRequest, UserResponse, AuthResponse,
)
from app.services import auth_service
from app.services.pin_service import build_user_response
from app.core.dependencies import get_current_user
from app.models.models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=201)
def register(
    payload: RegisterRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    """Register a new customer. OTP will be sent to the selected verification channel."""
    user = auth_service.register_user(
        db=db,
        full_name=payload.full_name,
        email=payload.email,
        phone_number=payload.phone_number,
        password=payload.password,
        verification_channel=payload.verification_channel,
        background_tasks=background_tasks,
        ip_address=request.client.host,
    )
    return build_user_response(user)


@router.post("/verify-otp")
def verify_otp(
    payload: OTPVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Verify email or phone with the OTP sent via the selected channel."""
    return auth_service.verify_otp(
        db=db,
        identifier=payload.identifier,
        otp_code=payload.otp_code,
        ip_address=request.client.host,
    )


@router.post("/login")
def login(
    payload: LoginRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    """Start login with email or phone and password. OTP is required before tokens are issued."""
    return auth_service.login_user(
        db=db,
        identifier=payload.identifier,
        password=payload.password,
        background_tasks=background_tasks,
        ip_address=request.client.host,
    )


@router.post("/login/verify-otp", response_model=AuthResponse)
def verify_login_otp(
    payload: LoginOTPVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Complete login with the OTP sent after valid email/phone + password authentication."""
    result = auth_service.verify_login_otp(
        db=db,
        identifier=payload.identifier,
        otp_code=payload.otp_code,
        ip_address=request.client.host,
    )
    return {
        "access_token": result["access_token"],
        "refresh_token": result["refresh_token"],
        "token_type": "bearer",
        "user": build_user_response(result["user"]),
    }


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    """Send a password reset OTP to the registered email or phone number."""
    return auth_service.request_password_reset(
        db=db,
        identifier=payload.identifier,
        background_tasks=background_tasks,
        ip_address=request.client.host,
    )


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Reset password using the OTP sent by the forgot-password endpoint."""
    return auth_service.reset_password(
        db=db,
        identifier=payload.identifier,
        otp_code=payload.otp_code,
        new_password=payload.new_password,
        ip_address=request.client.host,
    )


@router.post("/refresh")
def refresh(
    payload: RefreshRequest,
    db: Session = Depends(get_db),
):
    """Get a new access token using a valid refresh token."""
    return auth_service.refresh_access_token(
        db=db,
        refresh_token=payload.refresh_token,
    )


@router.post("/logout")
def logout(
    payload: LogoutRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Invalidate the refresh token (server-side logout)."""
    return auth_service.logout_user(
        db=db,
        refresh_token=payload.refresh_token,
        user_id=current_user.id,
        ip_address=request.client.host,
    )
