from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_active_customer
from app.models.models import User
from app.schemas.schemas import KYCUpgradeRequest
from app.services import kyc_service

router = APIRouter(prefix="/kyc", tags=["KYC"])


@router.post("/upgrade")
def upgrade_kyc(
    payload: KYCUpgradeRequest,
    request: Request,
    current_user: User = Depends(get_current_active_customer),
    db: Session = Depends(get_db),
):
    """Upgrade from Tier 1 to Tier 2 using a simulated NIN verification."""
    return kyc_service.upgrade_kyc(
        db=db,
        user=current_user,
        nin=payload.nin,
        ip_address=request.client.host,
    )


@router.get("/status")
def kyc_status(current_user: User = Depends(get_current_active_customer)):
    """Get current KYC tier and transfer limits."""
    return kyc_service.get_kyc_status(current_user)