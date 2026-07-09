from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from app.config import settings

mail_config = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
)


async def send_reset_email(to_email: str, reset_link: str):
    message = MessageSchema(
        subject="Reset your password",
        recipients=[to_email],
        body=f"""
        <p>You requested a password reset.</p>
        <p><a href="{reset_link}">Click here to reset your password</a></p>
        <p>This link expires in 30 minutes. If you didn't request this, ignore this email.</p>
        """,
        subtype=MessageType.html,
    )
    fm = FastMail(mail_config)
    await fm.send_message(message)

async def send_verification_email(to_email: str, code: str):
    message = MessageSchema(
        subject="Verify your email",
        recipients=[to_email],
        body=f"""
        <p>Your verification code is:</p>
        <h2>{code}</h2>
        <p>This code expires in 15 minutes.</p>
        """,
        subtype=MessageType.html,
    )
    fm = FastMail(mail_config)
    await fm.send_message(message)