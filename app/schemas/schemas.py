from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from decimal import Decimal
from datetime import datetime
from app.models.models import KYCTier, AccountStatus, TransactionStatus


# ── Auth Schemas ──────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    phone_number: str
    password: str
    verification_channel: str = "sms"

    @field_validator("verification_channel")
    @classmethod
    def channel_is_valid(cls, v):
        if v.lower() not in {"sms", "email"}:
            raise ValueError("Verification channel must be SMS or Email")
        return v.lower()

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("full_name")
    @classmethod
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Full name cannot be empty")
        return v


class OTPVerifyRequest(BaseModel):
    identifier: str
    otp_code: str


class LoginRequest(BaseModel):
    identifier: str
    password: str


class LoginOTPVerifyRequest(BaseModel):
    identifier: str
    otp_code: str


class ForgotPasswordRequest(BaseModel):
    identifier: str


class ResetPasswordRequest(BaseModel):
    identifier: str
    otp_code: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ── Account Schemas ───────────────────────────────────────────────────────────

class AccountResponse(BaseModel):
    account_number: str
    available_balance: Decimal
    ledger_balance: Decimal
    status: AccountStatus

    model_config = {"from_attributes": True}


class BalanceResponse(BaseModel):
    account_number: str
    available_balance: Decimal
    ledger_balance: Decimal
    currency: str = "NGN"


class UserResponse(BaseModel):
    id: str
    full_name: str
    email: str
    phone_number: str
    kyc_tier: KYCTier
    account_status: AccountStatus
    phone_verified: bool
    nin_verified: bool
    has_transfer_pin: bool = False
    created_at: datetime
    account: Optional[AccountResponse] = None

    model_config = {"from_attributes": True}


class ProfileResponse(UserResponse):
    transfer_single_limit_ngn: Optional[Decimal] = None
    transfer_daily_limit_ngn: Optional[Decimal] = None


class TransferPinStatusResponse(BaseModel):
    has_transfer_pin: bool


class SetTransferPinRequest(BaseModel):
    pin: str
    confirm_pin: str
    current_pin: Optional[str] = None

    @field_validator("pin", "confirm_pin")
    @classmethod
    def pin_must_be_four_digits(cls, v):
        if not v.isdigit() or len(v) != 4:
            raise ValueError("PIN must be exactly 4 digits")
        return v

    @field_validator("confirm_pin")
    @classmethod
    def pins_must_match(cls, v, info):
        if "pin" in info.data and v != info.data["pin"]:
            raise ValueError("PIN confirmation does not match")
        return v


# ── Transfer Schemas ──────────────────────────────────────────────────────────

class AuthResponse(TokenResponse):
    user: UserResponse


class TransferRequest(BaseModel):
    receiver_account_number: str
    amount: Decimal
    transfer_pin: str
    narration: Optional[str] = "Transfer"
    idempotency_key: Optional[str] = None

    @field_validator("transfer_pin")
    @classmethod
    def transfer_pin_format(cls, v):
        if not v.isdigit() or len(v) != 4:
            raise ValueError("Transfer PIN must be exactly 4 digits")
        return v

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v):
        if v <= 0:
            raise ValueError("Amount must be greater than zero")
        return v


class TransactionResponse(BaseModel):
    id: str
    reference: str
    amount: Decimal
    narration: Optional[str]
    status: TransactionStatus
    created_at: datetime
    sender_account_id: Optional[str] = None
    receiver_account_id: Optional[str] = None

    model_config = {"from_attributes": True}


# ── KYC Schemas ───────────────────────────────────────────────────────────────

class KYCUpgradeRequest(BaseModel):
    nin: str

    @field_validator("nin")
    @classmethod
    def nin_length(cls, v):
        if len(v) != 11 or not v.isdigit():
            raise ValueError("NIN must be exactly 11 digits")
        return v


class TopupRequest(BaseModel):
    amount: Decimal
    card_number: str = "**** **** **** ****"
    card_cvc: str = "***"
    card_expiry: str = "**/**"

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v):
        if v <= 0:
            raise ValueError("Amount must be greater than zero")
        return v

    @field_validator("amount")
    @classmethod
    def amount_max(cls, v):
        if v > Decimal("500000"):
            raise ValueError("Single top-up cannot exceed \u20A6 500,000")
        return v


# ── Admin Schemas ─────────────────────────────────────────────────────────────

class FreezeAccountRequest(BaseModel):
    account_number: str
    reason: Optional[str] = None


class DeleteUserRequest(BaseModel):
    reason: Optional[str] = None
