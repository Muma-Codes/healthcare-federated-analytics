"""
Email alert notifications for security events:
  - Account lockouts (too many failed logins)
  - Suspicious access patterns
  - Data breach detection alerts
  - Mandatory training reminders

Uses smtplib with Gmail SMTP (or any SMTP server).
Configure SMTP_* settings in .env before enabling.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import settings

logger = logging.getLogger(__name__)


async def send_alert_email(subject: str, body: str, to: str | None = None) -> bool:
    """
    Send a plain-text security alert email.
    Returns True on success, False on failure (never raises — alerts must not break the app).
    """
    recipient = to or settings.ALERT_EMAIL

    # Silently skip if SMTP is not configured
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD or not recipient:
        logger.warning("Email alert skipped: SMTP not configured. Subject: %s", subject)
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[{settings.APP_NAME}] {subject}"
        msg["From"]    = settings.SMTP_USER
        msg["To"]      = recipient

        text_body = MIMEText(body, "plain")
        msg.attach(text_body)

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USER, recipient, msg.as_string())

        logger.info("Alert email sent: %s → %s", subject, recipient)
        return True

    except Exception as exc:
        logger.error("Failed to send alert email: %s", exc)
        return False


async def notify_account_locked(username: str, ip: str):
    await send_alert_email(
        subject=f"Account Locked: {username}",
        body=(
            f"The account '{username}' has been locked after "
            f"{settings.MAX_LOGIN_ATTEMPTS} consecutive failed login attempts.\n\n"
            f"Source IP: {ip}\n\n"
            "Action required: Review audit logs and unlock the account if legitimate."
        ),
    )


async def notify_suspicious_access(username: str, resource: str, ip: str):
    await send_alert_email(
        subject=f"Suspicious Access Attempt: {username}",
        body=(
            f"User '{username}' attempted to access a restricted resource.\n\n"
            f"Resource: {resource}\n"
            f"Source IP: {ip}\n\n"
            "Please review the audit log immediately."
        ),
    )


async def notify_data_breach(detail: str):
    await send_alert_email(
        subject="SECURITY ALERT: Potential Data Breach Detected",
        body=(
            f"A potential data breach event has been detected.\n\n"
            f"Details:\n{detail}\n\n"
            "Immediate action is required. Engage your incident response procedure."
        ),
    )


async def notify_password_expiry_reminder(username: str, email: str, days_remaining: int):
    await send_alert_email(
        subject=f"Password Expiry Reminder: {days_remaining} days remaining",
        body=(
            f"Dear {username},\n\n"
            f"Your password will expire in {days_remaining} day(s).\n"
            "Please log in and change your password before it expires to avoid being locked out.\n\n"
            "If you did not receive this message in error, contact your administrator."
        ),
        to=email,
    )