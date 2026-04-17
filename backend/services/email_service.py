import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, html_body: str) -> bool:
    host = os.getenv("SMTP_HOST", "")
    if not host:
        logger.warning("SMTP_HOST not set — email skipped")
        return False
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    from_email = os.getenv("SMTP_FROM_EMAIL", "noreply@flowcut.ai")
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(host, port) as smtp:
            smtp.ehlo()
            smtp.starttls()
            if user:
                smtp.login(user, password)
            smtp.sendmail(from_email, to_email, msg.as_string())
        return True
    except Exception as e:
        logger.error("SMTP error sending to %s: %s", to_email, e)
        return False
