import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
from app.db.session import SessionLocal
from app.models.models import User, Account, AccountStatus, KYCTier
import uuid, random, string

def create_admin():
    db = SessionLocal()
    try:
        password = "AdminSecure1234"
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

        admin = User(
            id=str(uuid.uuid4()),
            full_name="Super Admin",
            email="admin@smartbank.admin",
            phone_number="08000000001",
            password_hash=hashed,
            kyc_tier=KYCTier.TIER_3,
            account_status=AccountStatus.ACTIVE,
            phone_verified=True,
            nin_verified=True,
        )
        db.add(admin)
        db.flush()

        account_number = "30" + "".join(random.choices(string.digits, k=8))
        db.add(Account(user_id=admin.id, account_number=account_number))
        db.commit()
        print(f"Admin created: admin@smartbank.admin / {password}")
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()