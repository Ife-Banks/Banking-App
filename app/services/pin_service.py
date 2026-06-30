from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security import hash_transfer_pin, verify_transfer_pin
from app.models.models import AuditLog, User


def user_has_transfer_pin(user: User) -> bool:
    return bool(user.transfer_pin_hash)


def build_user_response(user: User):
    from app.schemas.schemas import UserResponse

    data = UserResponse.model_validate(user).model_dump()
    data["has_transfer_pin"] = user_has_transfer_pin(user)
    return UserResponse(**data)


def build_profile_response(user: User):
    from app.schemas.schemas import ProfileResponse
    from app.services.transfer_service import TIER_LIMITS

    limits = TIER_LIMITS.get(user.kyc_tier, {})
    data = build_user_response(user).model_dump()
    data["transfer_single_limit_ngn"] = limits.get("single")
    data["transfer_daily_limit_ngn"] = limits.get("daily")
    return ProfileResponse(**data)


def get_transfer_pin_status(user: User) -> dict:
    return {"has_transfer_pin": user_has_transfer_pin(user)}


def set_transfer_pin(
    db: Session,
    user: User,
    pin: str,
    confirm_pin: str,
    current_pin: str | None = None,
) -> dict:
    if pin != confirm_pin:
        raise HTTPException(status_code=422, detail="PIN confirmation does not match")

    has_pin = user_has_transfer_pin(user)
    if has_pin:
        if not current_pin:
            raise HTTPException(status_code=400, detail="Current transfer PIN is required to change it")
        if not verify_transfer_pin(current_pin, user.transfer_pin_hash):
            raise HTTPException(status_code=400, detail="Current transfer PIN is incorrect")
        if current_pin == pin:
            raise HTTPException(status_code=400, detail="New PIN must be different from your current PIN")
        action = "transfer_pin_changed"
    else:
        action = "transfer_pin_set"

    user.transfer_pin_hash = hash_transfer_pin(pin)
    db.add(AuditLog(user_id=user.id, action=action, meta_data={}))
    db.commit()
    db.refresh(user)
    return {"message": "Transfer PIN saved successfully", "has_transfer_pin": True}


def verify_user_transfer_pin(user: User, pin: str) -> None:
    if not user_has_transfer_pin(user):
        raise HTTPException(
            status_code=400,
            detail="Transfer PIN not set. Set your 4-digit PIN in Profile before sending money.",
        )
    if not verify_transfer_pin(pin, user.transfer_pin_hash):
        raise HTTPException(status_code=400, detail="Incorrect transfer PIN")
