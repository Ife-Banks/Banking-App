from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_admin
from app.db.session import get_db
from app.models.models import User
from app.schemas.schemas import (
    DeleteUserRequest, FreezeAccountRequest, TransactionResponse, UserResponse,
)
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/users")
def list_users(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """List all registered users with pagination."""
    result = admin_service.list_users(db, limit, offset)
    return {
        "total": result["total"],
        "users": [UserResponse.model_validate(u) for u in result["users"]],
        "limit": limit,
        "offset": offset,
    }


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Get full profile for a specific user."""
    return admin_service.get_user_detail(db, user_id)


@router.post("/users/{user_id}/delete")
def delete_user(
    user_id: str,
    payload: DeleteUserRequest = DeleteUserRequest(),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Close a customer account (soft delete). Admin accounts cannot be deleted."""
    return admin_service.delete_user(
        db=db,
        user_id=user_id,
        reason=payload.reason,
        admin_user=admin,
    )


@router.post("/freeze-account")
def freeze_account(
    payload: FreezeAccountRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Freeze a customer account. Prevents all transactions."""
    return admin_service.freeze_account(
        db=db,
        account_number=payload.account_number,
        reason=payload.reason,
        admin_user=admin,
    )


@router.post("/unfreeze-account")
def unfreeze_account(
    payload: FreezeAccountRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Restore a frozen account to active status."""
    return admin_service.unfreeze_account(
        db=db,
        account_number=payload.account_number,
        admin_user=admin,
    )


@router.get("/transactions")
def list_transactions(
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """List all transactions. Filter by status: pending, successful, failed, reversed."""
    result = admin_service.list_transactions(db, limit, offset, status)
    return {
        "total": result["total"],
        "transactions": [TransactionResponse.model_validate(t) for t in result["transactions"]],
        "limit": limit,
        "offset": offset,
    }


@router.get("/transactions/{reference}", response_model=TransactionResponse)
def get_transaction(
    reference: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Get full transaction detail by reference."""
    return admin_service.get_transaction_detail(db, reference)


@router.get("/audit-logs")
def list_audit_logs(
    limit: int = 50,
    offset: int = 0,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """
    Inspect immutable audit trail. Filter by user_id or action.
    Action values: user_registered, login_success, login_failed, transfer_completed,
                   kyc_upgraded, account_frozen, account_unfrozen, user_deleted, logout
    """
    return admin_service.list_audit_logs(db, limit, offset, user_id, action)


@router.get("/stats")
def platform_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Platform-wide statistics: user counts, transaction volume, frozen accounts."""
    return admin_service.get_platform_stats(db)