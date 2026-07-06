# Maxtrader Content Engine

Turns the trading agent's data into publishable content: daily portfolio
reports, weekly performance reviews, and short-form social posts.

Reads the same `trades.json` the dashboard uses (written by
`src/trading/trades_logger.py`), so it needs no API keys or market data to
produce a report. Optionally, drafts can be rewritten into polished narrative
with the Claude API.

This directory is deliberately self-contained (own `pyproject.toml`, no
imports from the rest of Maxtrader) so it can be lifted into its own
`content-engine` repository unchanged.

## Usage

```bash
# From this directory (Maxtrader/content_engine) — no dependencies required
cd content_engine
python -m content_engine daily            # print today's report to stdout
python -m content_engine weekly           # weekly review
python -m content_engine social           # tweet-length update

# Write to files instead of stdout
python -m content_engine daily --out ../reports/

# Point at a specific trades.json (default: ../trades.json at the repo root)
python -m content_engine daily --trades /path/to/trades.json
```

To run from anywhere, either set `PYTHONPATH=/path/to/Maxtrader/content_engine`
or install it (`pip install -e .`), which also provides the `content-engine`
console script.

## Optional: Claude-polished narrative

```bash
pip install anthropic          # or: pip install -e ".[llm]"
export ANTHROPIC_API_KEY=sk-ant-...
python -m content_engine weekly --polish
```

`--polish` sends the template draft to Claude (`claude-opus-4-8` by default,
override with `--model`) with instructions to improve the prose without
changing any numbers. If the SDK or key is missing, or the API call fails,
the unpolished draft is used — content generation never hard-fails on the
LLM step.

## Content types

| Command  | Output | Contents |
|----------|--------|----------|
| `daily`  | Markdown | Equity/cash snapshot, open positions table, today's trades |
| `weekly` | Markdown | 7-day performance, buy/sell totals, most-traded tickers, positions |
| `social` | Plain text | Tweet-length session summary (< 280 chars) |

## Automation

Generate a report after each trading day, e.g. via cron:

```cron
30 21 * * 1-5 cd /path/to/Maxtrader/content_engine && python -m content_engine daily --out ../reports/
0  22 * * 5   cd /path/to/Maxtrader/content_engine && python -m content_engine weekly --out ../reports/
```

## Tests

```bash
cd content_engine && python -m pytest tests/ -v
```
