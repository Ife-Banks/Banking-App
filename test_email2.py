import asyncio
import sys
sys.path.insert(0, ".")

async def test():
    print("1. Checking API key...")
    from app.core.config import settings
    print(f"   RESEND_API_KEY: {settings.RESEND_API_KEY[:10]}...")
    print(f"   RESEND_FROM_EMAIL: {settings.RESEND_FROM_EMAIL}")

    print("\n2. Checking _has_resend_api_key...")
    from app.services.resend import _has_resend_api_key
    print(f"   Has key: {_has_resend_api_key()}")

    print("\n3. Testing send_otp_via_resend directly...")
    from app.services.resend import send_otp_via_resend
    try:
        await send_otp_via_resend("ifeoluwa.bankole05@gmail.com", "111222", "Test User")
        print("   SUCCESS!")
    except Exception as e:
        print(f"   ERROR: {e}")

    print("\n4. Testing send_otp_email (notification service)...")
    from app.services.notification_service import send_otp_email
    try:
        await send_otp_email("ifeoluwa.bankole05@gmail.com", "333444", "Test User")
        print("   SUCCESS!")
    except Exception as e:
        print(f"   ERROR: {e}")

    print("\n5. Checking OTP creation...")
    from app.db.session import SessionLocal
    from app.models.models import OTPToken
    db = SessionLocal()
    otps = db.query(OTPToken).order_by(OTPToken.created_at.desc()).limit(3).all()
    for o in otps:
        print(f"   OTP: {o.code} -> {o.contact_value} ({o.purpose})")
    db.close()

asyncio.run(test())