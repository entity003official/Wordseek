from __future__ import annotations

import smtplib
from email.message import EmailMessage

from ..core.config import settings


def send_password_reset(email: str, token: str) -> bool:
    if not settings.smtp_host or not settings.smtp_from:
        return False
    link = f"{settings.frontend_url.rstrip('/')}/reset-password?token={token}"
    message = EmailMessage()
    message["Subject"] = "重置 Beyond Words 密码"
    message["From"] = settings.smtp_from
    message["To"] = email
    message.set_content(f"请在 30 分钟内使用以下链接重置密码：\n\n{link}\n\n如果不是你本人操作，请忽略此邮件。")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
    return True
