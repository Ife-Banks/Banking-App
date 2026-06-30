import sys
sys.path.insert(0, ".")
from app.main import app
from app.schemas.schemas import RegisterRequest
from app.services import auth_service
from app.db.session import SessionLocal
import traceback

db = SessionLocal()
try:
    user = auth_service.register_user(
        db=db,
        full_name="Test User",
        email="test2@example.com",
        phone_number="08098765432",
        password="Test1234",
        verification_channel="sms",
        background_tasks=[],
        ip_address="127.0.0.1",
    )
    print("SUCCESS:", user)
except Exception as e:
    print("ERROR:", e)
    traceback.print_exc()
finally:
    db.close()