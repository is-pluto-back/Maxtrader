"""X (Twitter) publisher — posts social threads via the v2 API.

Requires an OAuth 2.0 *user-context* access token with ``tweet.write``
scope (from the X developer portal's OAuth 2.0 flow, or a token manager
like typefully/publer if you prefer). Set:

    TWITTER_OAUTH2_ACCESS_TOKEN=...

Threads are posted tweet-by-tweet with ``reply.in_reply_to_tweet_id``
chaining. Content generated as one document is posted as a single tweet
if it fits.
"""

import os
import time

import requests

from . import BasePublisher, PublishResult
from ..generator import GeneratedContent

TWEET_LIMIT = 280


class TwitterPublisher(BasePublisher):
    name = "twitter"

    def is_configured(self) -> bool:
        return bool(os.getenv("TWITTER_OAUTH2_ACCESS_TOKEN"))

    def _post_tweet(self, text: str, reply_to: str = None) -> dict:
        payload = {"text": text[:TWEET_LIMIT]}
        if reply_to:
            payload["reply"] = {"in_reply_to_tweet_id": reply_to}
        r = requests.post(
            "https://api.twitter.com/2/tweets",
            headers={
                "Authorization": f"Bearer {os.getenv('TWITTER_OAUTH2_ACCESS_TOKEN')}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["data"]

    def publish(self, content: GeneratedContent) -> PublishResult:
        tweets = [t.strip() for t in content.body.split("\n---\n") if t.strip()]
        if not tweets:
            return PublishResult(self.name, False, "no content")
        try:
            first = self._post_tweet(tweets[0])
            prev_id = first["id"]
            for t in tweets[1:]:
                time.sleep(2)  # be gentle with rate limits
                prev_id = self._post_tweet(t, reply_to=prev_id)["id"]
            return PublishResult(
                self.name, True, f"thread of {len(tweets)}, first id={first['id']}"
            )
        except Exception as e:
            return PublishResult(self.name, False, str(e))
