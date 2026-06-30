import asyncio
import sys
sys.path.insert(0, ".")
from app.services.notification_service import send_otp_email
from app.core.config import settings

print(f"RESEND_API_KEY: {settings.RESEND_API_KEY[:10]}...")
print(f"RESEND_FROM_EMAIL: {settings.RESEND_FROM_EMAIL}")

async def test():
    try:
        await send_otp_email("ifeoluwa.bankole05@gmail.com", "999888", "Test User")
        print("SUCCESS: Email sent!")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test())