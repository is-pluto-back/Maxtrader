"""Buttondown newsletter publisher.

Buttondown (buttondown.com) is a simple newsletter platform with a free
tier, built-in *paid subscriptions* (the primary revenue lever of this
pipeline), and a one-call API. Setup:

    BUTTONDOWN_API_KEY=...

Each publish creates and sends an email to all subscribers. Swap this
class for beehiiv/ConvertKit by implementing the same two methods.
"""

import os

import requests

from . import BasePublisher, PublishResult
from ..generator import GeneratedContent


class ButtondownPublisher(BasePublisher):
    name = "buttondown"

    def is_configured(self) -> bool:
        return bool(os.getenv("BUTTONDOWN_API_KEY"))

    def publish(self, content: GeneratedContent) -> PublishResult:
        try:
            r = requests.post(
                "https://api.buttondown.com/v1/emails",
                headers={
                    "Authorization": f"Token {os.getenv('BUTTONDOWN_API_KEY')}",
                    "Content-Type": "application/json",
                },
                json={
                    "subject": content.title,
                    "body": content.body,
                    "status": "about_to_send",
                },
                timeout=30,
            )
            r.raise_for_status()
            return PublishResult(self.name, True, f"email id={r.json().get('id')}")
        except Exception as e:
            return PublishResult(self.name, False, str(e))
