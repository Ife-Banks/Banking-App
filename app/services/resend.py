import asyncio
import resend

from app.core.config import settings

PLACEHOLDER_API_KEYS = {"", "re_gH7KLd3b_LCcSazCZ8K7DNb1YpRgHf4KS", "your-resend-key"}


def _has_resend_api_key() -> bool:
    api_key = settings.RESEND_API_KEY.strip()
    return bool(api_key) and api_key not in PLACEHOLDER_API_KEYS


def _build_otp_html(otp_code: str, full_name: str) -> str:
    first_name = full_name.split()[0] if full_name.split() else "there"
    return (
        f"<p>Hello {first_name},</p>"
        f"<p>Your SmartBank verification code is <strong>{otp_code}</strong>.</p>"
        "<p>It is valid for 10 minutes. Do not share this code with anyone.</p>"
        "<p>If you did not request this, please ignore this message.</p>"
    )


async def send_otp_via_resend(to_email: str, otp_code: str, full_name: str) -> None:
    if not _has_resend_api_key():
        raise RuntimeError("Resend API key is not configured")

    resend.api_key = settings.RESEND_API_KEY
    params: resend.Emails.SendParams = {
        "from": settings.RESEND_FROM_EMAIL,
        "to": [to_email],
        "subject": "SmartBank verification code",
        "html": _build_otp_html(otp_code, full_name),
    }
    await asyncio.to_thread(resend.Emails.send, params)
