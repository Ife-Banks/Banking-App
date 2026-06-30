import sys
sys.path.insert(0, ".")
from app.main import app
from app.schemas.schemas import TopupRequest
from app.routers.accounts import topup_account
from app.db.session import SessionLocal
from app.models.models import User
from app.core.dependencies import get_current_user
from fastapi import Depends
import traceback

db = SessionLocal()
try:
    user = db.query(User).filter(User.phone_number == "08100000002").first()
    if not user:
        print("User not found, trying first user...")
        user = db.query(User).first()

    print(f"Testing with user: {user.full_name} ({user.phone_number})")

    payload = TopupRequest(
        amount="5000",
        card_number="4242424242424242",
        card_cvc="123",
        card_expiry="12/28"
    )

    result = topup_account(
        payload=payload,
        current_user=user,
        db=db
    )
    print("SUCCESS:", result)

except Exception as e:
    print("ERROR:", e)
    traceback.print_exc()
finally:
    db.close()