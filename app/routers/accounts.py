from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload
from decimal import Decimal

from app.db.session import get_db
from app.core.dependencies import get_current_active_customer
from app.models.models import User, Transaction, Account, LedgerEntry
from app.schemas.schemas import (
    UserResponse,
    ProfileResponse,
    TransactionResponse,
    BalanceResponse,
    TransferPinStatusResponse,
    SetTransferPinRequest,
    TopupRequest,
)
from app.services import pin_service
from app.models.models import TransactionStatus, TransactionType, EntryType

router = APIRouter(prefix="/accounts", tags=["Accounts"])


def _load_user(db: Session, user_id: str) -> User:
    return (
        db.query(User)
        .options(joinedload(User.account))
        .filter(User.id == user_id)
        .first()
    )


@router.get("/me", response_model=ProfileResponse)
def get_profile(
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db),
):
    """Get current user profile, account details, and transfer limits."""
    user = _load_user(db, current_user.id) or current_user
    return pin_service.build_profile_response(user)


@router.get("/transfer-pin/status", response_model=TransferPinStatusResponse)
def transfer_pin_status(current_user: User = Depends(get_current_active_customer)):
    return pin_service.get_transfer_pin_status(current_user)


@router.post("/transfer-pin")
def set_transfer_pin(
    payload: SetTransferPinRequest,
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db),
):
    """Create or change the 4-digit PIN required for outgoing transfers."""
    return pin_service.set_transfer_pin(
        db=db,
        user=current_user,
        pin=payload.pin,
        confirm_pin=payload.confirm_pin,
        current_pin=payload.current_pin,
    )


@router.get("/balance", response_model=BalanceResponse)
def get_balance(current_user: User = Depends(get_current_active_customer)):
    """Get available and ledger balance."""
    account = current_user.account
    return {
        "account_number": account.account_number,
        "available_balance": float(account.available_balance),
        "ledger_balance": float(account.ledger_balance),
        "currency": "NGN",
    }


@router.get("/transactions")
def get_transactions(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db),
):
    """Paginated transaction history for the current account."""
    account_id = current_user.account.id
    transactions = (
        db.query(Transaction)
        .filter(
            (Transaction.sender_account_id == account_id)
            | (Transaction.receiver_account_id == account_id)
        )
        .order_by(Transaction.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "transactions": [TransactionResponse.model_validate(t) for t in transactions],
        "count": len(transactions),
        "offset": offset,
    }


@router.post("/topup")
def topup_account(
    payload: TopupRequest,
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db),
):
    """Add funds to the user's account via card top-up."""
    from uuid import UUID
    from app.models.models import gen_uuid

    account = current_user.account
    if not account:
        raise HTTPException(status_code=400, detail="Account not found")

    amount_dec = Decimal(str(payload.amount))
    masked_card = f"Card ...{payload.card_number[-4:]}"

    balance_before = Decimal(str(account.available_balance))
    balance_after = balance_before + amount_dec

    account_id = UUID(account.id) if isinstance(account.id, str) else account.id

    txn = Transaction(
        id=gen_uuid(),
        reference=f"TPX{gen_uuid().replace('-', '')[:12].upper()}",
        amount=amount_dec,
        narration=f"Top-up via {masked_card}",
        transaction_type=TransactionType.TOPUP,
        status=TransactionStatus.SUCCESSFUL,
        sender_account_id=account_id,
        receiver_account_id=account_id,
    )
    db.add(txn)
    db.flush()

    ledger_entry = LedgerEntry(
        id=gen_uuid(),
        transaction_id=txn.id,
        account_id=account_id,
        entry_type=EntryType.CREDIT,
        amount=amount_dec,
        balance_before=balance_before,
        balance_after=balance_after,
    )
    db.add(ledger_entry)

    account.available_balance = float(balance_after)
    account.ledger_balance = float(balance_after)

    db.commit()
    db.refresh(account)
    db.refresh(txn)

    return {
        "reference": txn.reference,
        "amount": float(amount_dec),
        "new_balance": float(account.available_balance),
        "message": f"\u20A6{float(amount_dec):,.2f} added to your account",
    }
