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
