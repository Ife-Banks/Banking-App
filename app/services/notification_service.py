import asyncio
import smtplib
from email.message import EmailMessage
import httpx

from app.core.config import settings
from app.services.resend import _has_resend_api_key, send_otp_via_resend


TERMII_SMS_URL = "https://api.ng.termii.com/api/sms/send"
PLACEHOLDER_API_KEYS = {"your_termii_key", "your-termii-key"}


def _has_termii_api_key() -> bool:
    api_key = settings.TERMII_API_KEY.strip()
    return bool(api_key) and api_key not in PLACEHOLDER_API_KEYS


async def send_otp_sms(phone_number: str, otp_code: str, full_name: str):
    """
    Sends OTP via Termii. Called as a BackgroundTask; failures are logged, not raised.
    During development you can leave TERMII_API_KEY empty or as the placeholder value.
    """
    if not _has_termii_api_key():
        print(f"\n[DEV OTP] {phone_number} -> {otp_code}\n")
        return

    first_name = full_name.split()[0] if full_name.split() else "there"
    message = (
        f"Hello {first_name}, your SmartBank verification code is {otp_code}. "
        "Valid for 10 minutes. Do not share this code."
    )

    payload = {
        "to": phone_number,
        "from": settings.TERMII_SENDER_ID,
        "sms": message,
        "type": "plain",
        "api_key": settings.TERMII_API_KEY,
        "channel": "generic",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(TERMII_SMS_URL, json=payload)
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        print(
            f"[SMS ERROR] Failed to send OTP to {phone_number}: "
            f"{e.response.status_code} {e.response.text}"
        )
    except Exception as e:
        print(f"[SMS ERROR] Failed to send OTP to {phone_number}: {e}")


def _has_smtp_settings() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USERNAME and settings.SMTP_PASSWORD)


def _build_email_message(to_email: str, otp_code: str, full_name: str) -> EmailMessage:
    first_name = full_name.split()[0] if full_name.split() else "there"
    message = EmailMessage()
    message["Subject"] = "SmartBank verification code"
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = to_email
    message.set_content(
        f"Hello {first_name},\n\nYour SmartBank verification code is {otp_code}.\n"
        "It is valid for 10 minutes. Do not share this code with anyone.\n\n"
        "If you did not request this, please ignore this message.\n"
    )
    return message


def _send_email_smtp(message: EmailMessage):
    if settings.SMTP_USE_SSL:
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(message)
    else:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(message)


async def send_otp_email(email: str, otp_code: str, full_name: str):
    """Send OTP by Resend, SMTP, or console fallback (in that order)."""
    if _has_resend_api_key():
        try:
            await send_otp_via_resend(email, otp_code, full_name)
            return
        except Exception as e:
            print(f"[EMAIL ERROR] Resend failed for {email}: {e}")
            return

    if _has_smtp_settings():
        message = _build_email_message(email, otp_code, full_name)
        try:
            await asyncio.to_thread(_send_email_smtp, message)
            return
        except Exception as e:
            print(f"[EMAIL ERROR] SMTP failed for {email}: {e}")
            return

    print(f"\n[DEV OTP EMAIL] {email} -> {otp_code}\n")


async def send_transaction_alert(phone_number: str, message: str):
    """Generic SMS used for debit/credit alerts."""
    if not _has_termii_api_key():
        print(f"\n[DEV SMS] {phone_number} -> {message}\n")
        return

    payload = {
        "to": phone_number,
        "from": settings.TERMII_SENDER_ID,
        "sms": message,
        "type": "plain",
        "api_key": settings.TERMII_API_KEY,
        "channel": "generic",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(TERMII_SMS_URL, json=payload)
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        print(f"[SMS ERROR] {e.response.status_code} {e.response.text}")
    except Exception as e:
        print(f"[SMS ERROR] {e}")
