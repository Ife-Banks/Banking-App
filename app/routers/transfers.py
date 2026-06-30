from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_active_customer
from app.models.models import User
from app.schemas.schemas import TransferRequest, TransactionResponse
from app.services import transfer_service, receipt_service

router = APIRouter(prefix="/transfers", tags=["Transfers"])


@router.post("/internal", response_model=TransactionResponse, status_code=201)
def internal_transfer(
    payload: TransferRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db),
):
    """
    Transfer funds to another SmartBank account.
    Idempotency: pass a unique idempotency_key to safely retry without double-charging.
    """
    txn = transfer_service.internal_transfer(
        db=db,
        sender_user=current_user,
        receiver_account_number=payload.receiver_account_number,
        amount=payload.amount,
        transfer_pin=payload.transfer_pin,
        narration=payload.narration or "Transfer",
        idempotency_key=payload.idempotency_key,
        background_tasks=background_tasks,
    )
    return txn


@router.get("/{reference}/receipt")
def download_receipt(
    reference: str,
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db),
):
    """Download an HTML transaction receipt (open in browser or print to PDF)."""
    txn = receipt_service.get_transaction_for_user(db, reference, current_user)
    html = receipt_service.build_receipt_html(txn, current_user.account.id)
    filename = f"SmartBank-Receipt-{reference}.html"
    return HTMLResponse(
        content=html,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{reference}", response_model=TransactionResponse)
def get_transaction(
    reference: str,
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db),
):
    """Look up a transaction by reference. Only the sender or receiver can view it."""
    return receipt_service.get_transaction_for_user(db, reference, current_user)