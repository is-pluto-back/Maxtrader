"""Telegram channel publisher.

Setup: create a bot with @BotFather, add it as an admin to your public
channel, then set:

    TELEGRAM_BOT_TOKEN=123456:ABC-...
    TELEGRAM_CHAT_ID=@your_channel   (or a numeric chat id)

A Telegram channel is a strong free distribution surface for trading
content and converts well to newsletter signups.
"""

import os

import requests

from . import BasePublisher, PublishResult
from ..generator import GeneratedContent

MAX_LEN = 4000  # Telegram hard limit is 4096


class TelegramPublisher(BasePublisher):
    name = "telegram"

    def is_configured(self) -> bool:
        return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))

    def publish(self, content: GeneratedContent) -> PublishResult:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        text = content.body.replace("\n---\n", "\n\n")  # threads read as one post
        if len(text) > MAX_LEN:
            text = text[: MAX_LEN - 20] + "\n\n[truncated]"
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True,
                },
                timeout=30,
            )
            data = r.json()
            if not data.get("ok"):
                # Markdown parse errors are common; retry as plain text.
                r = requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": text},
                    timeout=30,
                )
                data = r.json()
            if data.get("ok"):
                return PublishResult(
                    self.name, True, f"message_id={data['result']['message_id']}"
                )
            return PublishResult(self.name, False, str(data.get("description")))
        except Exception as e:
            return PublishResult(self.name, False, str(e))
