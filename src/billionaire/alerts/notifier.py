"""Lightweight multi-channel alerter. Channels are pluggable — a null channel
is always active so logging never fails. All calls are best-effort; failures
do not raise."""

from __future__ import annotations

import logging
import smtplib
import threading
from abc import ABC, abstractmethod
from email.mime.text import MIMEText
from typing import Any

import httpx

from billionaire.config import get_settings

log = logging.getLogger(__name__)


class AlertChannel(ABC):
    name: str = "base"

    @abstractmethod
    def send(self, subject: str, body: str, **meta: Any) -> None: ...


class ConsoleChannel(AlertChannel):
    name = "console"

    def send(self, subject: str, body: str, **meta: Any) -> None:
        log.info("[ALERT] %s :: %s", subject, body)


class TelegramChannel(AlertChannel):
    name = "telegram"

    def __init__(self, token: str, chat_id: str) -> None:
        self.token = token
        self.chat_id = chat_id

    def send(self, subject: str, body: str, **meta: Any) -> None:
        if not (self.token and self.chat_id):
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        try:
            httpx.post(url, json={"chat_id": self.chat_id, "text": f"*{subject}*\n{body}",
                                  "parse_mode": "Markdown"}, timeout=5.0)
        except (httpx.HTTPError, OSError) as e:  # pragma: no cover
            log.warning("telegram send failed: %s", e)


class EmailChannel(AlertChannel):
    name = "email"

    def __init__(self, host: str, port: int, user: str, password: str, sender: str, recipient: str) -> None:
        self.host, self.port = host, port
        self.user, self.password = user, password
        self.sender, self.recipient = sender, recipient

    def send(self, subject: str, body: str, **meta: Any) -> None:
        if not (self.host and self.sender and self.recipient):
            return
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = self.recipient
        try:
            with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
                smtp.starttls()
                if self.user and self.password:
                    smtp.login(self.user, self.password)
                smtp.sendmail(self.sender, [self.recipient], msg.as_string())
        except (smtplib.SMTPException, OSError) as e:  # pragma: no cover
            log.warning("email send failed: %s", e)


class Alerter:
    def __init__(self, channels: list[AlertChannel] | None = None) -> None:
        self._channels: list[AlertChannel] = list(channels or [])
        self._lock = threading.RLock()

    @classmethod
    def from_settings(cls) -> Alerter:
        s = get_settings()
        channels: list[AlertChannel] = []
        if s.alerts_console:
            channels.append(ConsoleChannel())
        if s.telegram_bot_token and s.telegram_chat_id:
            channels.append(TelegramChannel(s.telegram_bot_token, s.telegram_chat_id))
        if s.smtp_host and s.smtp_from and s.smtp_to:
            channels.append(EmailChannel(s.smtp_host, s.smtp_port, s.smtp_user, s.smtp_password, s.smtp_from, s.smtp_to))
        return cls(channels)

    def add(self, channel: AlertChannel) -> None:
        with self._lock:
            self._channels.append(channel)

    def send(self, subject: str, body: str, **meta: Any) -> None:
        with self._lock:
            channels = list(self._channels)
        for ch in channels:
            try:
                ch.send(subject, body, **meta)
            except (RuntimeError, OSError) as e:  # pragma: no cover
                log.warning("channel %s failed: %s", ch.name, e)
