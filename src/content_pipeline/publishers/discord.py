"""Discord publisher via channel webhook.

Setup: in your Discord server, Channel Settings -> Integrations ->
Webhooks -> New Webhook, then set:

    DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
"""

import os

import requests

from . import BasePublisher, PublishResult
from ..generator import GeneratedContent

MAX_LEN = 1900  # Discord limit is 2000/message


class DiscordPublisher(BasePublisher):
    name = "discord"

    def is_configured(self) -> bool:
        return bool(os.getenv("DISCORD_WEBHOOK_URL"))

    def publish(self, content: GeneratedContent) -> PublishResult:
        url = os.getenv("DISCORD_WEBHOOK_URL")
        text = content.body.replace("\n---\n", "\n\n")
        chunks = [text[i : i + MAX_LEN] for i in range(0, len(text), MAX_LEN)] or [""]
        try:
            for chunk in chunks[:3]:  # cap at 3 messages per post
                r = requests.post(
                    url,
                    json={"content": chunk, "username": self.cfg.brand.name},
                    timeout=30,
                )
                r.raise_for_status()
            return PublishResult(self.name, True, f"{min(len(chunks), 3)} message(s)")
        except Exception as e:
            return PublishResult(self.name, False, str(e))
