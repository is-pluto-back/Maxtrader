# Maxtrader Content Engine

An autonomous content-revenue pipeline built on top of the trading system.

The trading agent already produces something genuinely scarce every day:
a real quant model's regime read, rotation targets, and portfolio P&L.
This pipeline turns that exhaust into published, monetized content —
automatically, on a schedule, with no manual step:

```
snapshot ──> generate ──> monetize ──> publish ──> ledger
 (market      (LLM or      (CTAs,       (blog,      (what went
  + strategy   templates)   affiliates,  Telegram,    where + revenue
  state)                    sponsors)    Discord, X,  tracking)
                                         newsletter)
```

## Quick start (zero configuration)

Works immediately, no API keys, no network:

```bash
python run_content_pipeline.py --dry-run --offline --provider template
```

This generates a daily brief and a social thread from whatever data is
available (or clearly-flagged demo data), applies monetization blocks,
and saves previews to `content/generated/` without publishing anywhere.
Read the previews — that's exactly what would have been posted.

## Going live: the 30-minute setup

### 1. Pick your LLM (optional but recommended)

```
# .env — first available wins; templates are the no-key fallback
ANTHROPIC_API_KEY=...      # preferred
OPENAI_API_KEY=...         # fallback (already used elsewhere in this repo)
```

### 2. Connect channels (each is optional)

| Channel | Setup | Env vars |
|---|---|---|
| **Blog** | none — writes Jekyll/Hugo markdown to `content/posts/` | (always on) |
| **Telegram** | create bot via @BotFather, make it channel admin | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| **Discord** | channel webhook (Integrations → Webhooks) | `DISCORD_WEBHOOK_URL` |
| **X/Twitter** | OAuth 2.0 user token, `tweet.write` scope | `TWITTER_OAUTH2_ACCESS_TOKEN` |
| **Buttondown** | Settings → API on buttondown.com | `BUTTONDOWN_API_KEY` |

Unconfigured channels are skipped silently — connect them one at a time.

For the blog, enable GitHub Pages on this repo (or any Jekyll/Hugo site)
pointed at `content/posts/`. Every daily brief becomes an SEO-indexable
page that compounds organic search traffic over time.

### 3. Configure the brand & monetization

Edit `content_pipeline.yaml`:

- **brand** — name, tagline, voice (drives the LLM's writing style)
- **monetization.newsletter_signup_url** — your Buttondown page
- **monetization.premium_url** — your paid tier
- **monetization.affiliates** — products with keywords; links are
  auto-inserted (with UTM tracking) only when relevant to the post
- **monetization.sponsor_slot** — paste sponsor copy when a slot is sold

### 4. Schedule it

```bash
python run_content_pipeline.py schedule   # prints ready-to-paste cron lines
crontab -e
```

Default cadence: daily brief + social thread every weekday 45 min after
the close; weekly newsletter on Sunday. After this, the pipeline runs
itself.

## Media generation (images, video, voiceover)

Every run also produces visual media, with the same "works with zero
keys, gets better with keys" tiering:

| Asset | No keys needed | With keys |
|---|---|---|
| **Image cards** (1080×1080) | Pillow-rendered branded market + rotation cards | + AI hero image via OpenAI (`media.use_ai_images: true`) |
| **Video script** | Template SCENE/VISUAL/VO script | LLM-written 60-second short script |
| **Voiceover** | — (video is silent) | ElevenLabs (`ELEVENLABS_API_KEY`) or OpenAI TTS |
| **Daily short** (1080×1920 MP4) | ffmpeg slideshow of the day's frames + voiceover | same, with better script/voice |

ffmpeg is resolved from PATH or from `pip install imageio-ffmpeg` (a
bundled static binary — no system install). Media attaches automatically:
Telegram gets the photo/video, Discord gets attachments, the blog embeds
the market card, X attaches the card to the first tweet (when the token
has `media.write` scope). Configure under `media:` in
`content_pipeline.yaml`; disable with `enable_images: false` /
`enable_video: false`.

## Deploying to Vercel (public site + autonomous cron)

The `web/` directory is a self-contained Vercel project:

- **`/`** — public landing page that renders today's brief, thread,
  newsletter, and video script live (SEO surface + newsletter funnel)
- **`/api/brief?type=…`** — JSON API generating content on demand
  (edge-cached 15 min)
- **`/api/cron`** — the autonomous heartbeat: Vercel Cron calls it
  weekdays at 21:45 UTC (45 min after the US close) and it generates +
  publishes to every channel configured via env vars

### Deploy steps (~5 minutes)

1. Push this repo to GitHub (already done if you're reading this on GitHub).
2. On [vercel.com/new](https://vercel.com/new), import the repo and set
   **Root Directory = `web`** (framework preset "Other"). Or from a
   terminal: `cd web && npx vercel --prod`.
3. In the Vercel project → Settings → Environment Variables, add:
   - `CRON_SECRET` — any long random string (protects `/api/cron`)
   - `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` — for LLM-written content
   - any channel credentials (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
     `DISCORD_WEBHOOK_URL`, `TWITTER_OAUTH2_ACCESS_TOKEN`,
     `BUTTONDOWN_API_KEY`) — each channel activates automatically
4. Redeploy. The cron schedule in `web/vercel.json` activates on the
   production deployment — after that the pipeline is fully autonomous.

### Notes

- The pipeline package is vendored into `web/_vendor/` so the deploy
  needs nothing outside `web/`. After changing `src/content_pipeline/`,
  run `python web/sync_vendor.py` (a test fails if you forget).
- Vercel's filesystem is read-only except `/tmp`, so on Vercel the blog
  channel is ephemeral; durable blog posts come from running the cron
  variant in the repo (crontab or GitHub Actions). The API-based
  channels (Telegram/Discord/X/Buttondown) are unaffected.
- Video rendering is skipped on Vercel by default (serverless CPU/time
  limits); set `VERCEL_ENABLE_VIDEO=1` to try it, or render videos from
  the repo cron.
- Test locally first: `python web/dev_server.py` serves the exact same
  handlers at `http://localhost:3000`.

## The revenue model

Content alone doesn't make money — the funnel does. This pipeline builds
the standard, proven finance-content funnel:

1. **Reach** (free): daily X threads, Telegram, Discord posts create
   discovery. The blog compounds SEO traffic.
2. **Own** (free → asset): every piece of content carries a newsletter
   CTA. The email list is the durable asset that platforms can't take
   away.
3. **Monetize** (three levers, all automated in `monetizer.py`):
   - **Paid newsletter tier** — Buttondown/beehiiv paid subscriptions
     for position-level detail ($5–15/mo is standard for signal letters)
   - **Affiliate revenue** — broker/charting/data-tool links inserted
     contextually with UTM tracking so you can attribute conversions
   - **Sponsor slot** — once the list has a few thousand readers, a
     weekly sponsored placement is a standard $50–500+ per issue

Track money as it arrives:

```bash
python run_content_pipeline.py revenue 125.50 --source newsletter --note "July payout"
python run_content_pipeline.py stats
```

## Realistic expectations

Automation removes the labor, not the ramp. Audiences take months to
build; affiliate and sponsor revenue follow list size. What this
pipeline guarantees is *consistency* — the single biggest failure mode
of content businesses — at near-zero marginal cost per post. The
quality ceiling comes from your strategy's actual signal being
interesting, which is the moat generic AI-content operations don't have.

## Compliance guardrails (built-in, do not remove)

- Every long-form piece carries a "not financial advice" disclaimer
  (configurable text in `content_pipeline.yaml`, appended automatically).
- The LLM system prompt forbids direct buy/sell advice, promised
  returns, and fabricated numbers; generation is grounded in the
  snapshot facts only.
- Demo data is always explicitly flagged, never presented as live.

If you publish performance figures, keep them accurate and consider
your jurisdiction's rules on investment communications.

## CLI reference

```bash
python run_content_pipeline.py                          # publish today's due content
python run_content_pipeline.py --dry-run                # generate + preview only
python run_content_pipeline.py --types newsletter       # force a specific piece
python run_content_pipeline.py --provider template      # skip LLMs
python run_content_pipeline.py --offline                # no network data fetches
python run_content_pipeline.py stats                    # publish counts + revenue
python run_content_pipeline.py revenue <amt> --source X # log revenue
python run_content_pipeline.py schedule                 # cron lines
```

## Architecture

```
src/content_pipeline/
├── config.py        # content_pipeline.yaml + env secrets
├── snapshot.py      # market + strategy state (trades.json, weights, Stooq)
├── generator.py     # Anthropic -> OpenAI -> template fallback chain
├── templates.py     # deterministic zero-key content generation
├── monetizer.py     # CTAs, affiliates (UTM), sponsor slot, disclaimer
├── ledger.py        # data/content_ledger.json — publishes + revenue
├── pipeline.py      # orchestrator
└── publishers/      # blog, telegram, discord, twitter, buttondown
```

Adding a channel = one file implementing `is_configured()` and
`publish()`, plus a registry entry in `publishers/__init__.py`.
