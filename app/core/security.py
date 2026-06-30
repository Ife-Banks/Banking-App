from datetime import datetime, timedelta
from typing import Optional
import hashlib
import secrets

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

BCRYPT_ROUNDS = 12


# ── Passwords ─────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    password_bytes = plain.encode("utf-8")
    if len(password_bytes) > 72:
        raise ValueError("Password cannot be longer than 72 bytes")

    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    password_bytes = plain.encode("utf-8")
    if len(password_bytes) > 72:
        return False

    try:
        return bcrypt.checkpw(password_bytes, hashed.encode("utf-8"))
    except ValueError:
        return False


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "type": "access", "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": user_id, "type": "refresh", "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Returns the payload dict, or None if the token is invalid/expired."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


# ── Refresh token storage helpers ─────────────────────────────────────────────

def hash_refresh_token(token: str) -> str:
    """We store a hash of the refresh token, not the raw token."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_otp() -> str:
    """Cryptographically secure 6-digit OTP."""
    return str(secrets.randbelow(900000) + 100000)


# ── Transfer PIN (4 digits, stored like passwords) ────────────────────────────

def validate_transfer_pin(pin: str) -> str:
    if not pin.isdigit() or len(pin) != 4:
        raise ValueError("Transfer PIN must be exactly 4 digits")
    return pin


def hash_transfer_pin(pin: str) -> str:
    return hash_password(validate_transfer_pin(pin))


def verify_transfer_pin(pin: str, hashed: Optional[str]) -> bool:
    if not hashed:
        return False
    try:
        validate_transfer_pin(pin)
    except ValueError:
        return False
    return verify_password(pin, hashed)
