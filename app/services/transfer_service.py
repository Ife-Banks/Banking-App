import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import (
    Account, AuditLog, KYCTier, LedgerEntry,
    Transaction, TransactionStatus, TransactionType, EntryType, User,
)
from app.services.notification_service import send_transaction_alert


# ── KYC tier limits ───────────────────────────────────────────────────────────

TIER_LIMITS = {
    KYCTier.TIER_1: {"single": Decimal("20000"),  "daily": Decimal("50000")},
    KYCTier.TIER_2: {"single": Decimal("200000"), "daily": Decimal("500000")},
    KYCTier.TIER_3: {"single": Decimal("5000000"),"daily": Decimal("5000000")},
}


def _generate_reference() -> str:
    return f"SB{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"


def _get_daily_total(db: Session, account_id: str) -> Decimal:
    """Sum all successful outgoing transfers today."""
    today_start = datetime.combine(date.today(), datetime.min.time())
    result = db.query(func.sum(Transaction.amount)).filter(
        Transaction.sender_account_id == account_id,
        Transaction.status == TransactionStatus.SUCCESSFUL,
        Transaction.created_at >= today_start,
    ).scalar()
    return Decimal(str(result or 0))


def _write_ledger(
    db: Session,
    transaction_id: str,
    account_id: str,
    entry_type: EntryType,
    amount: Decimal,
    balance_before: Decimal,
    balance_after: Decimal,
):
    entry = LedgerEntry(
        transaction_id=transaction_id,
        account_id=account_id,
        entry_type=entry_type,
        amount=amount,
        balance_before=balance_before,
        balance_after=balance_after,
    )
    db.add(entry)


def _log_audit(db: Session, action: str, user_id: str, meta: dict):
    db.add(AuditLog(user_id=user_id, action=action, meta_data=meta))


# ── Main transfer function ────────────────────────────────────────────────────

def internal_transfer(
    db: Session,
    sender_user: User,
    receiver_account_number: str,
    amount: Decimal,
    transfer_pin: str,
    narration: str,
    idempotency_key: Optional[str],
    background_tasks: BackgroundTasks,
) -> Transaction:

    from app.services.pin_service import verify_user_transfer_pin

    verify_user_transfer_pin(sender_user, transfer_pin)

    # ── 1. Idempotency check ──────────────────────────────────────────────────
    if idempotency_key:
        existing = db.query(Transaction).filter(
            Transaction.idempotency_key == idempotency_key
        ).first()
        if existing:
            return existing  # identical request — return cached result

    # ── 2. Resolve accounts ───────────────────────────────────────────────────
    sender_account = sender_user.account
    if not sender_account:
        raise HTTPException(status_code=400, detail="Sender account not found")

    receiver_account = db.query(Account).filter(
        Account.account_number == receiver_account_number
    ).first()
    if not receiver_account:
        raise HTTPException(status_code=404, detail="Receiver account not found")

    if sender_account.account_number == receiver_account_number:
        raise HTTPException(status_code=400, detail="Cannot transfer to your own account")

    # ── 3. KYC limit enforcement ──────────────────────────────────────────────
    limits = TIER_LIMITS[sender_user.kyc_tier]

    if amount > limits["single"]:
        raise HTTPException(
            status_code=400,
            detail=f"Amount exceeds your single transfer limit of ₦{limits['single']:,.2f} (Tier {sender_user.kyc_tier.value})"
        )

    daily_total = _get_daily_total(db, sender_account.id)
    if daily_total + amount > limits["daily"]:
        remaining = limits["daily"] - daily_total
        raise HTTPException(
            status_code=400,
            detail=f"Transfer would exceed your daily limit. Remaining today: ₦{remaining:,.2f}"
        )

    # ── 4. Balance check ──────────────────────────────────────────────────────
    if sender_account.available_balance < amount:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance. Available: ₦{sender_account.available_balance:,.2f}"
        )

    # ── 5. Atomic DB transaction ──────────────────────────────────────────────
    try:
        # Create transaction record (pending)
        txn = Transaction(
            reference=_generate_reference(),
            sender_account_id=sender_account.id,
            receiver_account_id=receiver_account.id,
            amount=amount,
            narration=narration or "Transfer",
            transaction_type=TransactionType.TRANSFER,
            status=TransactionStatus.PENDING,
            idempotency_key=idempotency_key,
        )
        db.add(txn)
        db.flush()  # get txn.id without committing

        # Debit sender
        sender_balance_before = sender_account.available_balance
        sender_account.available_balance -= amount
        sender_account.ledger_balance -= amount
        _write_ledger(
            db, txn.id, sender_account.id,
            EntryType.DEBIT, amount,
            sender_balance_before,
            sender_account.available_balance,
        )

        # Credit receiver
        receiver_balance_before = receiver_account.available_balance
        receiver_account.available_balance += amount
        receiver_account.ledger_balance += amount
        _write_ledger(
            db, txn.id, receiver_account.id,
            EntryType.CREDIT, amount,
            receiver_balance_before,
            receiver_account.available_balance,
        )

        # Mark successful
        txn.status = TransactionStatus.SUCCESSFUL

        # Audit
        _log_audit(db, "transfer_completed", sender_user.id, {
            "reference": txn.reference,
            "amount": str(amount),
            "receiver": receiver_account_number,
        })

        db.commit()
        db.refresh(txn)

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Transfer failed: {str(e)}")

    # ── 6. SMS alerts (non-blocking, after commit) ────────────────────────────
    sender_name = sender_user.full_name.split()[0]
    receiver_user = receiver_account.user

    background_tasks.add_task(
        send_transaction_alert,
        sender_user.phone_number,
        f"Debit: ₦{amount:,.2f} from your SmartBank account to {receiver_account_number}. "
        f"Ref: {txn.reference}. Balance: ₦{sender_account.available_balance:,.2f}",
    )
    if receiver_user:
        background_tasks.add_task(
            send_transaction_alert,
            receiver_user.phone_number,
            f"Credit: ₦{amount:,.2f} received in your SmartBank account from {sender_name}. "
            f"Ref: {txn.reference}. Balance: ₦{receiver_account.available_balance:,.2f}",
        )

    return txn
