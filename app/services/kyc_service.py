from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.models import AuditLog, IdentityRegistry, KYCTier, User, VerificationStatus


def upgrade_kyc(db: Session, user: User, nin: str, ip_address: str) -> dict:
    if user.kyc_tier != KYCTier.TIER_1:
        raise HTTPException(
            status_code=400,
            detail=f"Already at {user.kyc_tier.value}. Contact admin for Tier 3 upgrade."
        )

    # Look up NIN in the simulated identity registry
    record = db.query(IdentityRegistry).filter(
        IdentityRegistry.nin == nin,
        IdentityRegistry.verification_status == VerificationStatus.VERIFIED,
    ).first()

    if not record:
        raise HTTPException(status_code=400, detail="NIN not found in identity registry")

    # Optional: check name similarity (loose match)
    user_name_lower = user.full_name.lower()
    registry_name_lower = record.full_name.lower()
    user_parts = set(user_name_lower.split())
    registry_parts = set(registry_name_lower.split())
    if not user_parts.intersection(registry_parts):
        raise HTTPException(
            status_code=400,
            detail="NIN details do not match your registered name"
        )

    # Upgrade
    user.kyc_tier = KYCTier.TIER_2
    user.nin_verified = True

    db.add(AuditLog(
        user_id=user.id,
        action="kyc_upgraded",
        ip_address=ip_address,
        meta_data={"from": "tier_1", "to": "tier_2", "nin_prefix": nin[:4] + "XXXXXXX"},
    ))

    db.commit()
    db.refresh(user)

    return {
        "message": "KYC upgraded to Tier 2 successfully",
        "kyc_tier": user.kyc_tier.value,
        "new_limits": {
            "single_transfer": "₦200,000",
            "daily_transfer": "₦500,000",
        }
    }


def get_kyc_status(user: User) -> dict:
    limits = {
        KYCTier.TIER_1: {"single": "₦20,000",  "daily": "₦50,000"},
        KYCTier.TIER_2: {"single": "₦200,000", "daily": "₦500,000"},
        KYCTier.TIER_3: {"single": "₦5,000,000","daily": "₦5,000,000"},
    }
    return {
        "kyc_tier": user.kyc_tier.value,
        "phone_verified": user.phone_verified,
        "nin_verified": user.nin_verified,
        "limits": limits[user.kyc_tier],
    }
