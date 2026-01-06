
import os
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr
from typing import List

# Configuration
MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
MAIL_FROM = os.getenv("MAIL_FROM", "")
MAIL_PORT = 587
MAIL_SERVER = "smtp.gmail.com"
MAIL_FROM_NAME = "DB Project Auth"

conf = ConnectionConfig(
    MAIL_USERNAME=MAIL_USERNAME,
    MAIL_PASSWORD=MAIL_PASSWORD,
    MAIL_FROM=MAIL_FROM,
    MAIL_PORT=MAIL_PORT,
    MAIL_SERVER=MAIL_SERVER,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

async def send_verification_email(email_to: str, code: str):
    """
    Sends a verification code to the user's email.
    """
    if not MAIL_PASSWORD:
        print(f"[Email Service] Mock Send -> To: {email_to}, Code: {code}")
        return

    html = f"""
    <h3>Email Verification</h3>
    <p>Your verification code is:</p>
    <h2 style="color: #007bff;">{code}</h2>
    <p>Please enter this code in the application to verify your account.</p>
    """

    message = MessageSchema(
        subject="Your Verification Code",
        recipients=[email_to],
        body=html,
        subtype=MessageType.html
    )

    fm = FastMail(conf)
    try:
        await fm.send_message(message)
        print(f"[Email Service] Email sent to {email_to}")
    except Exception as e:
        print(f"[Email Service] Failed to send email: {e}")
