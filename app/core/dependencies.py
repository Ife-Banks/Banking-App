from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, joinedload

from app.core.security import decode_token
from app.db.session import get_db
from app.models.models import User, AccountStatus

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Decodes the JWT, looks up the user, and returns them.
    Raises 401 if the token is missing, expired, or invalid.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise credentials_exception

    user_id: str = payload.get("sub")
    if not user_id:
        raise credentials_exception

    user = (
        db.query(User)
        .options(joinedload(User.account))
        .filter(User.id == user_id)
        .first()
    )
    if not user:
        raise credentials_exception

    return user


def get_current_active_customer(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Extends get_current_user — also checks the account isn't frozen/suspended.
    Use this on all customer-facing endpoints.
    """
    if current_user.account_status == AccountStatus.FROZEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is frozen. Contact support.",
        )
    if current_user.account_status == AccountStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended.",
        )
    if current_user.account_status == AccountStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been closed.",
        )
    return current_user


def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Use this on all /admin/* endpoints."""
    from app.models.models import KYCTier  # avoid circular import
    # In a real system you'd have a separate is_admin flag or role field.
    # For now, super admin is anyone whose email ends in @smartbank.admin
    if not current_user.email.endswith("@smartbank.admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
