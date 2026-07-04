"""Blog publisher: writes Jekyll/Hugo-compatible markdown posts.

Always configured — it needs no credentials. Point GitHub Pages (or any
static site generator) at ``content/posts/`` and every daily brief
becomes an SEO-indexable page that compounds organic traffic, which is
what the affiliate links and newsletter CTAs convert.
"""

import re
from datetime import datetime

from . import BasePublisher, PublishResult
from ..generator import GeneratedContent


def slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9\s-]", "", text.lower())
    return re.sub(r"[\s-]+", "-", text).strip("-")[:60]


class BlogPublisher(BasePublisher):
    name = "blog"

    def is_configured(self) -> bool:
        return True

    def publish(self, content: GeneratedContent) -> PublishResult:
        self.cfg.blog_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        path = self.cfg.blog_dir / f"{today}-{slugify(content.title)}.md"

        # Copy attached images next to the post and embed the first one.
        body = content.body
        if content.images:
            assets = self.cfg.blog_dir / "assets"
            assets.mkdir(exist_ok=True)
            image = content.images[0]
            if image.exists():
                dest = assets / image.name
                dest.write_bytes(image.read_bytes())
                body = f"![{content.title}](assets/{image.name})\n\n{body}"

        front_matter = "\n".join(
            [
                "---",
                f'title: "{content.title}"',
                f"date: {today}",
                f"author: {self.cfg.brand.author}",
                f"categories: [{content.content_type.replace('_', '-')}]",
                "layout: post",
                "---",
                "",
            ]
        )
        path.write_text(front_matter + body + "\n")
        return PublishResult(self.name, True, str(path))
