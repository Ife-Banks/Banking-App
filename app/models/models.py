import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey,
    Numeric, String, Text, JSON, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.session import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class KYCTier(str, PyEnum):
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"


class AccountStatus(str, PyEnum):
    ACTIVE = "active"
    FROZEN = "frozen"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class TransactionStatus(str, PyEnum):
    PENDING = "pending"
    SUCCESSFUL = "successful"
    FAILED = "failed"
    REVERSED = "reversed"


class TransactionType(str, PyEnum):
    TRANSFER = "transfer"
    REVERSAL = "reversal"
    TOPUP = "topup"


class EntryType(str, PyEnum):
    DEBIT = "debit"
    CREDIT = "credit"


class VerificationStatus(str, PyEnum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"


# ── Helper ────────────────────────────────────────────────────────────────────

def gen_uuid():
    return str(uuid.uuid4())


# ── Models ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id               = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    full_name        = Column(String(150), nullable=False)
    email            = Column(String(255), unique=True, nullable=False, index=True)
    phone_number     = Column(String(20), unique=True, nullable=False, index=True)
    password_hash    = Column(String(255), nullable=False)
    kyc_tier         = Column(Enum(KYCTier), default=KYCTier.TIER_1, nullable=False)
    account_status   = Column(Enum(AccountStatus), default=AccountStatus.ACTIVE, nullable=False)
    phone_verified   = Column(Boolean, default=False, nullable=False)
    nin_verified     = Column(Boolean, default=False, nullable=False)
    transfer_pin_hash = Column(String(255), nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships — lets you do user.account, user.audit_logs
    account          = relationship("Account", back_populates="user", uselist=False)
    audit_logs       = relationship("AuditLog", back_populates="user")


class Account(Base):
    __tablename__ = "accounts"

    id                = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id           = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, unique=True)
    account_number    = Column(String(10), unique=True, nullable=False, index=True)
    available_balance = Column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    ledger_balance    = Column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    status            = Column(Enum(AccountStatus), default=AccountStatus.ACTIVE, nullable=False)
    created_at        = Column(DateTime, default=datetime.utcnow, nullable=False)

    user              = relationship("User", back_populates="account")
    sent_transactions = relationship("Transaction", foreign_keys="Transaction.sender_account_id", back_populates="sender")
    recv_transactions = relationship("Transaction", foreign_keys="Transaction.receiver_account_id", back_populates="receiver")


class Transaction(Base):
    __tablename__ = "transactions"

    id                  = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    reference           = Column(String(50), unique=True, nullable=False, index=True)
    sender_account_id   = Column(UUID(as_uuid=False), ForeignKey("accounts.id"), nullable=False)
    receiver_account_id = Column(UUID(as_uuid=False), ForeignKey("accounts.id"), nullable=False)
    amount              = Column(Numeric(18, 2), nullable=False)
    narration           = Column(String(255), default="Transfer")
    transaction_type    = Column(Enum(TransactionType), default=TransactionType.TRANSFER, nullable=False)
    status              = Column(Enum(TransactionStatus), default=TransactionStatus.PENDING, nullable=False)
    idempotency_key     = Column(String(100), unique=True, nullable=True, index=True)
    created_at          = Column(DateTime, default=datetime.utcnow, nullable=False)

    sender              = relationship("Account", foreign_keys=[sender_account_id], back_populates="sent_transactions")
    receiver            = relationship("Account", foreign_keys=[receiver_account_id], back_populates="recv_transactions")
    ledger_entries      = relationship("LedgerEntry", back_populates="transaction")


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id             = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    transaction_id = Column(UUID(as_uuid=False), ForeignKey("transactions.id"), nullable=False)
    account_id     = Column(UUID(as_uuid=False), ForeignKey("accounts.id"), nullable=False)
    entry_type     = Column(Enum(EntryType), nullable=False)
    amount         = Column(Numeric(18, 2), nullable=False)
    balance_before = Column(Numeric(18, 2), nullable=False)
    balance_after  = Column(Numeric(18, 2), nullable=False)
    created_at     = Column(DateTime, default=datetime.utcnow, nullable=False)

    transaction    = relationship("Transaction", back_populates="ledger_entries")

    __table_args__ = (
        Index("ix_ledger_account_txn", "account_id", "transaction_id"),
    )


class IdentityRegistry(Base):
    """Simulated NIN database — populated with seed data, not connected to real govt APIs."""
    __tablename__ = "identity_registry"

    id                  = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    nin                 = Column(String(11), unique=True, nullable=False, index=True)
    full_name           = Column(String(150), nullable=False)
    date_of_birth       = Column(String(20))
    phone_number        = Column(String(20))
    verification_status = Column(Enum(VerificationStatus), default=VerificationStatus.VERIFIED)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id         = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id    = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)  # nullable for system events
    action     = Column(String(100), nullable=False)
    ip_address = Column(String(50))
    meta_data   = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user       = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_user_action", "user_id", "action"),
    )


class OTPRecord(Base):
    __tablename__ = "otp_records"

    id            = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    contact_value = Column(String(255), nullable=False, index=True)
    otp_code      = Column(String(6), nullable=False)
    purpose       = Column(String(30), default="registration", nullable=False, index=True)
    expires_at    = Column(DateTime, nullable=False)
    verified      = Column(Boolean, default=False)
    created_at    = Column(DateTime, default=datetime.utcnow, nullable=False)


class RefreshToken(Base):
    """Stored so logout can invalidate tokens (not in the PRD tables but essential)."""
    __tablename__ = "refresh_tokens"

    id         = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id    = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked    = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
