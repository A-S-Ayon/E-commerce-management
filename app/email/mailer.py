import requests
from app.config import settings

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def _send_via_brevo(to_email: str, subject: str, html_content: str) -> None:
    response = requests.post(
        BREVO_API_URL,
        headers={
            "api-key": settings.BREVO_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "sender": {"email": settings.MAIL_FROM, "name": "Your Shop"},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html_content,
        },
        timeout=10,
    )
    response.raise_for_status()


async def send_reset_email(to_email: str, reset_link: str) -> None:
    html = f"""
    <p>You requested a password reset.</p>
    <p><a href="{reset_link}">Click here to reset your password</a></p>
    <p>This link expires in 30 minutes. If you didn't request this, ignore this email.</p>
    """
    _send_via_brevo(to_email, "Reset your password", html)


async def send_verification_email(to_email: str, code: str) -> None:
    html = f"""
    <p>Your verification code is:</p>
    <h2>{code}</h2>
    <p>This code expires in 15 minutes.</p>
    """
    _send_via_brevo(to_email, "Verify your email", html)