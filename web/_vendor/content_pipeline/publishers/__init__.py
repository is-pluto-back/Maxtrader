"""Channel publishers.

Each publisher declares whether it's configured (credentials present in
the environment); unconfigured channels are skipped silently so the
pipeline runs with whatever the user has connected — from nothing at all
(blog files only) to the full five-channel fan-out.
"""

from dataclasses import dataclass
from typing import Dict, Type

from ..config import PipelineConfig
from ..generator import GeneratedContent


@dataclass
class PublishResult:
    channel: str
    ok: bool
    detail: str = ""  # URL, message id, or error text


class BasePublisher:
    name = "base"

    def __init__(self, cfg: PipelineConfig):
        self.cfg = cfg

    def is_configured(self) -> bool:
        raise NotImplementedError

    def publish(self, content: GeneratedContent) -> PublishResult:
        raise NotImplementedError


from .blog import BlogPublisher  # noqa: E402
from .telegram import TelegramPublisher  # noqa: E402
from .discord import DiscordPublisher  # noqa: E402
from .twitter import TwitterPublisher  # noqa: E402
from .buttondown import ButtondownPublisher  # noqa: E402

PUBLISHERS: Dict[str, Type[BasePublisher]] = {
    "blog": BlogPublisher,
    "telegram": TelegramPublisher,
    "discord": DiscordPublisher,
    "twitter": TwitterPublisher,
    "buttondown": ButtondownPublisher,
}

__all__ = ["BasePublisher", "PublishResult", "PUBLISHERS"]
