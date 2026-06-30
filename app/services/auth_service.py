import random
import string
from datetime import datetime, timedelta
from typing import Optional

from pydantic import EmailStr, ValidationError, parse_obj_as
from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    hash_refresh_token, generate_otp,
)
from app.models.models import (
    User, Account, OTPRecord, RefreshToken,
    AuditLog, AccountStatus, KYCTier,
)
from app.services.notification_service import send_otp_email, send_otp_sms


OTP_PURPOSE_REGISTRATION = "registration"
OTP_PURPOSE_LOGIN = "login"
OTP_PURPOSE_PASSWORD_RESET = "password_reset"


def _normalize_contact(identifier: str) -> tuple[str, str]:
    identifier = identifier.strip()
    if "@" in identifier:
        try:
            identifier = parse_obj_as(EmailStr, identifier)
        except ValidationError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid email address",
            )
        return identifier.lower(), "email"
    return _validate_nigerian_phone(identifier), "phone"


def _create_otp_record(db: Session, contact_value: str, purpose: str) -> str:
    db.query(OTPRecord).filter(
        OTPRecord.contact_value == contact_value,
        OTPRecord.purpose == purpose,
        OTPRecord.verified == False,
    ).update({"verified": True}, synchronize_session=False)

    otp_code = generate_otp()
    otp_record = OTPRecord(
        contact_value=contact_value,
        otp_code=otp_code,
        purpose=purpose,
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db.add(otp_record)
    return otp_code


def _get_valid_otp_record(db: Session, contact_value: str, otp_code: str, purpose: str) -> OTPRecord:
    record = (
        db.query(OTPRecord)
        .filter(
            OTPRecord.contact_value == contact_value,
            OTPRecord.purpose == purpose,
            OTPRecord.verified == False,
        )
        .order_by(OTPRecord.created_at.desc())
        .first()
    )

    if not record:
        raise HTTPException(status_code=400, detail="No pending OTP for this contact")

    if datetime.utcnow() > record.expires_at:
        raise HTTPException(status_code=400, detail="OTP has expired. Request a new one.")

    if record.otp_code != otp_code:
        raise HTTPException(status_code=400, detail="Invalid OTP code")

    return record


# ── Helpers ───────────────────────────────────────────────────────────────────

def _generate_account_number(db: Session) -> str:
    """Generate a unique 10-digit account number starting with 30 (SmartBank prefix)."""
    while True:
        number = "30" + "".join(random.choices(string.digits, k=8))
        exists = db.query(Account).filter(Account.account_number == number).first()
        if not exists:
            return number


def _log_audit(db: Session, action: str, user_id: Optional[str], ip: Optional[str], meta: Optional[dict] = None):
    log = AuditLog(user_id=user_id, action=action, ip_address=ip, meta_data=meta or {})
    db.add(log)


def _validate_nigerian_phone(phone: str) -> str:
    """Normalize and validate. Accepts 08012345678 or +2348012345678."""
    phone = phone.strip().replace(" ", "")
    if phone.startswith("+234"):
        phone = "0" + phone[4:]
    if not phone.startswith("0") or len(phone) != 11 or not phone.isdigit():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid Nigerian phone number. Use format: 08012345678",
        )
    return phone


def _create_otp_record(db: Session, contact_value: str, purpose: str) -> str:
    db.query(OTPRecord).filter(
        OTPRecord.contact_value == contact_value,
        OTPRecord.purpose == purpose,
        OTPRecord.verified == False,
    ).update({"verified": True}, synchronize_session=False)

    otp_code = generate_otp()
    otp_record = OTPRecord(
        contact_value=contact_value,
        otp_code=otp_code,
        purpose=purpose,
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db.add(otp_record)
    return otp_code


def _get_valid_otp_record(db: Session, contact_value: str, otp_code: str, purpose: str) -> OTPRecord:
    record = (
        db.query(OTPRecord)
        .filter(
            OTPRecord.contact_value == contact_value,
            OTPRecord.purpose == purpose,
            OTPRecord.verified == False,
        )
        .order_by(OTPRecord.created_at.desc())
        .first()
    )

    if not record:
        raise HTTPException(status_code=400, detail="No pending OTP for this contact")

    if datetime.utcnow() > record.expires_at:
        raise HTTPException(status_code=400, detail="OTP has expired. Request a new one.")

    if record.otp_code != otp_code:
        raise HTTPException(status_code=400, detail="Invalid OTP code")

    return record


def _issue_tokens(db: Session, user: User) -> dict:
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(rt)
    return {"access_token": access_token, "refresh_token": refresh_token, "user": user}


# ── Register ──────────────────────────────────────────────────────────────────

def register_user(
    db: Session,
    full_name: str,
    email: str,
    phone_number: str,
    password: str,
    verification_channel: str,
    background_tasks: BackgroundTasks,
    ip_address: str,
) -> User:
    phone_number = _validate_nigerian_phone(phone_number)
    email = email.lower()
    verification_channel = verification_channel.lower()
    if verification_channel not in {"sms", "email"}:
        raise HTTPException(status_code=400, detail="Verification channel must be SMS or Email")

    # Check uniqueness
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(User).filter(User.phone_number == phone_number).first():
        raise HTTPException(status_code=400, detail="Phone number already registered")

    # Create user
    user = User(
        full_name=full_name.strip(),
        email=email,
        phone_number=phone_number,
        password_hash=hash_password(password),
        kyc_tier=KYCTier.TIER_1,
        account_status=AccountStatus.ACTIVE,
        phone_verified=False,
    )
    db.add(user)
    db.flush()  # flush so user.id is available before commit

    # Create linked account
    account = Account(
        user_id=user.id,
        account_number=_generate_account_number(db),
    )
    db.add(account)

    contact_value = email if verification_channel == "email" else phone_number
    otp_code = _create_otp_record(db, contact_value, OTP_PURPOSE_REGISTRATION)

    # Audit
    _log_audit(db, "user_registered", user.id, ip_address, {"email": email, "verification_channel": verification_channel})

    db.commit()
    db.refresh(user)

    # Send OTP in background (non-blocking)
    if verification_channel == "email":
        background_tasks.add_task(send_otp_email, email, otp_code, full_name)
    else:
        background_tasks.add_task(send_otp_sms, phone_number, otp_code, full_name)

    return user


# ── Verify OTP ────────────────────────────────────────────────────────────────

def verify_otp(db: Session, identifier: str, otp_code: str, ip_address: str) -> dict:
    identifier, contact_type = _normalize_contact(identifier)

    record = _get_valid_otp_record(db, identifier, otp_code, OTP_PURPOSE_REGISTRATION)
    record.verified = True
    user = db.query(User).filter(
        User.email == identifier if contact_type == "email" else User.phone_number == identifier
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found for verification")

    user.phone_verified = True
    _log_audit(db, "contact_verified", user.id, ip_address)

    db.commit()
    return {"message": f"{contact_type.capitalize()} verified successfully", "verified": True}


# ── Login ─────────────────────────────────────────────────────────────────────

def login_user(
    db: Session,
    identifier: str,
    password: str,
    background_tasks: BackgroundTasks,
    ip_address: str,
) -> dict:
    identifier, contact_type = _normalize_contact(identifier)
    user = db.query(User).filter(
        User.email == identifier if contact_type == "email" else User.phone_number == identifier
    ).first()

    # Deliberate: same error for wrong identifier AND wrong password (prevents enumeration)
    if not user or not verify_password(password, user.password_hash):
        _log_audit(db, "login_failed", None, ip_address, {"identifier": identifier})
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.phone_verified:
        raise HTTPException(status_code=403, detail="Account not verified. Complete registration verification first.")

    if user.account_status in (AccountStatus.FROZEN, AccountStatus.SUSPENDED, AccountStatus.CLOSED):
        raise HTTPException(status_code=403, detail=f"Account is {user.account_status.value}")

    otp_code = _create_otp_record(db, identifier, OTP_PURPOSE_LOGIN)
    _log_audit(db, "login_otp_requested", user.id, ip_address)
    db.commit()

    if contact_type == "email":
        background_tasks.add_task(send_otp_email, identifier, otp_code, user.full_name)
    else:
        background_tasks.add_task(send_otp_sms, identifier, otp_code, user.full_name)

    return {"message": "OTP sent. Complete verification to login."}


def verify_login_otp(db: Session, identifier: str, otp_code: str, ip_address: str) -> dict:
    identifier, contact_type = _normalize_contact(identifier)
    record = _get_valid_otp_record(db, identifier, otp_code, OTP_PURPOSE_LOGIN)
    user = db.query(User).filter(
        User.email == identifier if contact_type == "email" else User.phone_number == identifier
    ).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.account_status in (AccountStatus.FROZEN, AccountStatus.SUSPENDED, AccountStatus.CLOSED):
        raise HTTPException(status_code=403, detail=f"Account is {user.account_status.value}")

    record.verified = True
    result = _issue_tokens(db, user)
    _log_audit(db, "login_success", user.id, ip_address)
    db.commit()
    return result


def request_password_reset(
    db: Session,
    identifier: str,
    background_tasks: BackgroundTasks,
    ip_address: str,
) -> dict:
    identifier, contact_type = _normalize_contact(identifier)
    user = db.query(User).filter(
        User.email == identifier if contact_type == "email" else User.phone_number == identifier
    ).first()

    if user:
        otp_code = _create_otp_record(db, identifier, OTP_PURPOSE_PASSWORD_RESET)
        _log_audit(db, "password_reset_requested", user.id, ip_address)
        db.commit()
        if contact_type == "email":
            background_tasks.add_task(send_otp_email, identifier, otp_code, user.full_name)
        else:
            background_tasks.add_task(send_otp_sms, identifier, otp_code, user.full_name)
    else:
        _log_audit(db, "password_reset_requested_unknown_identifier", None, ip_address)
        db.commit()

    return {"message": "If the identifier exists, a password reset OTP has been sent."}


def reset_password(
    db: Session,
    identifier: str,
    otp_code: str,
    new_password: str,
    ip_address: str,
) -> dict:
    identifier, _ = _normalize_contact(identifier)
    record = _get_valid_otp_record(db, identifier, otp_code, OTP_PURPOSE_PASSWORD_RESET)
    user = db.query(User).filter(
        (User.email == identifier) | (User.phone_number == identifier)
    ).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid OTP code")

    record.verified = True
    user.password_hash = hash_password(new_password)
    _log_audit(db, "password_reset_completed", user.id, ip_address)
    db.commit()
    return {"message": "Password reset successfully"}


# ── Refresh ───────────────────────────────────────────────────────────────────

def refresh_access_token(db: Session, refresh_token: str) -> dict:
    from app.core.security import decode_token

    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    token_hash = hash_refresh_token(refresh_token)
    stored = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.revoked == False,
    ).first()

    if not stored or datetime.utcnow() > stored.expires_at:
        raise HTTPException(status_code=401, detail="Refresh token expired or revoked")

    new_access = create_access_token(payload["sub"])
    return {"access_token": new_access, "token_type": "bearer"}


# ── Logout ────────────────────────────────────────────────────────────────────

def logout_user(db: Session, refresh_token: str, user_id: str, ip_address: str) -> dict:
    token_hash = hash_refresh_token(refresh_token)
    stored = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.user_id == user_id,
    ).first()

    if stored:
        stored.revoked = True

    _log_audit(db, "logout", user_id, ip_address)
    db.commit()
    return {"message": "Logged out successfully"}
