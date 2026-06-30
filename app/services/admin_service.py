from decimal import Decimal
from typing import Optional
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.models import (
    Account, AccountStatus, AuditLog,
    RefreshToken, Transaction, TransactionStatus, User,
)

ADMIN_EMAIL_SUFFIX = "@smartbank.admin"


# ── User management ───────────────────────────────────────────────────────────

def list_users(db: Session, limit: int, offset: int) -> dict:
    total = db.query(func.count(User.id)).scalar()
    users = (
        db.query(User)
        .options(joinedload(User.account))
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {"total": total, "users": users, "limit": limit, "offset": offset}


def get_user_detail(db: Session, user_id: str) -> User:
    user = (
        db.query(User)
        .options(joinedload(User.account))
        .filter(User.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def delete_user(
    db: Session,
    user_id: str,
    reason: Optional[str],
    admin_user: User,
) -> dict:
    """Close a customer account: revoke sessions, anonymize PII, preserve audit history."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.email.endswith(ADMIN_EMAIL_SUFFIX):
        raise HTTPException(status_code=403, detail="Admin accounts cannot be deleted")

    if user.account_status == AccountStatus.CLOSED:
        raise HTTPException(status_code=400, detail="User account is already closed")

    account = user.account
    if account:
        balance = account.available_balance or Decimal("0")
        if balance > Decimal("0"):
            raise HTTPException(
                status_code=400,
                detail="Account must have zero balance before deletion",
            )
        account.status = AccountStatus.CLOSED

    user.account_status = AccountStatus.CLOSED
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.revoked == False,
    ).update({"revoked": True}, synchronize_session=False)

    original_email = user.email
    original_phone = user.phone_number
    tag = user.id.replace("-", "")[:12]
    user.email = f"deleted-{tag}@closed.smartbank"
    user.phone_number = f"9{tag}"[:20]
    user.full_name = "Deleted User"

    db.add(AuditLog(
        user_id=admin_user.id,
        action="user_deleted",
        meta_data={
            "target_user_id": user_id,
            "original_email": original_email,
            "original_phone": original_phone,
            "reason": reason or "No reason provided",
        },
    ))
    db.commit()
    return {"message": "User account closed and removed from active users"}


# ── Account freeze / unfreeze ─────────────────────────────────────────────────

def freeze_account(
    db: Session,
    account_number: str,
    reason: Optional[str],
    admin_user: User,
) -> dict:
    account = db.query(Account).filter(Account.account_number == account_number).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if account.status == AccountStatus.FROZEN:
        raise HTTPException(status_code=400, detail="Account is already frozen")

    account.status = AccountStatus.FROZEN
    account.user.account_status = AccountStatus.FROZEN

    db.add(AuditLog(
        user_id=admin_user.id,
        action="account_frozen",
        meta_data={
            "account_number": account_number,
            "reason": reason or "No reason provided",
            "target_user_id": account.user_id,
        },
    ))
    db.commit()
    return {"message": f"Account {account_number} frozen", "reason": reason}


def unfreeze_account(
    db: Session,
    account_number: str,
    admin_user: User,
) -> dict:
    account = db.query(Account).filter(Account.account_number == account_number).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if account.status != AccountStatus.FROZEN:
        raise HTTPException(status_code=400, detail="Account is not frozen")

    account.status = AccountStatus.ACTIVE
    account.user.account_status = AccountStatus.ACTIVE

    db.add(AuditLog(
        user_id=admin_user.id,
        action="account_unfrozen",
        meta_data={"account_number": account_number, "target_user_id": account.user_id},
    ))
    db.commit()
    return {"message": f"Account {account_number} unfrozen"}


# ── Transaction monitoring ────────────────────────────────────────────────────

def list_transactions(
    db: Session,
    limit: int,
    offset: int,
    status: Optional[str],
) -> dict:
    query = db.query(Transaction)
    if status:
        try:
            status_enum = TransactionStatus(status)
            query = query.filter(Transaction.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    total = query.count()
    transactions = query.order_by(Transaction.created_at.desc()).offset(offset).limit(limit).all()
    return {"total": total, "transactions": transactions, "limit": limit, "offset": offset}


def get_transaction_detail(db: Session, reference: str) -> Transaction:
    txn = db.query(Transaction).filter(Transaction.reference == reference).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return txn


# ── Audit logs ────────────────────────────────────────────────────────────────

def list_audit_logs(
    db: Session,
    limit: int,
    offset: int,
    user_id: Optional[str],
    action: Optional[str],
) -> dict:
    query = db.query(AuditLog)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)

    total = query.count()
    logs = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    return {"total": total, "logs": logs, "limit": limit, "offset": offset}


# ── Platform stats ────────────────────────────────────────────────────────────

def get_platform_stats(db: Session) -> dict:
    total_users = db.query(func.count(User.id)).scalar()
    verified_users = db.query(func.count(User.id)).filter(User.phone_verified == True).scalar()
    frozen_accounts = db.query(func.count(Account.id)).filter(
        Account.status == AccountStatus.FROZEN
    ).scalar()

    total_volume = db.query(func.sum(Transaction.amount)).filter(
        Transaction.status == TransactionStatus.SUCCESSFUL
    ).scalar() or Decimal("0")

    total_txns = db.query(func.count(Transaction.id)).filter(
        Transaction.status == TransactionStatus.SUCCESSFUL
    ).scalar()

    return {
        "total_users": total_users,
        "verified_users": verified_users,
        "frozen_accounts": frozen_accounts,
        "successful_transactions": total_txns,
        "total_volume_ngn": float(total_volume),
    }