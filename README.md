# FinRL Trading Agent

AI-powered stock trading system using the Adaptive Multi-Asset Rotation Strategy with Alpaca paper/live trading and a real-time monitoring dashboard.

## Quick Start

```bash
cd finrl-trading-agent

# Activate the virtual environment
source venv/bin/activate

# Add your Alpaca API keys (see below)
nano .env

# Run a backtest
python src/strategies/run_adaptive_rotation_strategy.py \
    --config src/strategies/AdaptiveRotationConf_v1.2.2.yaml \
    --backtest --start 2022-01-01 --end 2024-12-31

# Start the dashboard
cd dashboard && npm run dev
```

## 1. Alpaca API Keys

Edit the `.env` file in the project root:

```
APCA_API_KEY=your_alpaca_paper_key_here
APCA_API_SECRET=your_alpaca_paper_secret_here
APCA_BASE_URL=https://paper-api.alpaca.markets
```

Get paper trading keys at https://app.alpaca.markets/paper/dashboard/overview (sign up free, go to API Keys).

## 2. Switching from Paper to Live Trading

**Paper trading** (default, safe):
```
APCA_BASE_URL=https://paper-api.alpaca.markets
```

**Live trading** (real money):
```
APCA_BASE_URL=https://api.alpaca.markets
```

Use your **live** API key/secret (different from paper keys). Start with paper trading to validate the strategy before going live.

## 3. Running the Trading Agent

### Backtest (no API keys needed)

```bash
source venv/bin/activate

# Weekly rebalance only (fast, ~30 seconds)
python src/strategies/run_adaptive_rotation_strategy.py \
    --config src/strategies/AdaptiveRotationConf_v1.2.2.yaml \
    --backtest --start 2022-01-01 --end 2024-12-31 \
    --no-daily-fast-track

# With daily risk monitoring (slower, full feature set)
python src/strategies/run_adaptive_rotation_strategy.py \
    --config src/strategies/AdaptiveRotationConf_v1.2.2.yaml \
    --backtest --start 2022-01-01 --end 2024-12-31
```

Results are saved to `src/strategies/output/weights/adaptive_rotation/`.

### Live/Paper Trading

```bash
source venv/bin/activate
python src/main.py trade
```

The agent connects to Alpaca, generates target weights from the adaptive rotation strategy, and executes rebalance orders. Every trade is logged to `trades.json` for the dashboard.

### Single-Date Signal

```bash
python src/strategies/run_adaptive_rotation_strategy.py \
    --config src/strategies/AdaptiveRotationConf_v1.2.2.yaml \
    --date 2024-12-31
```

## 4. Monitoring Dashboard

```bash
cd dashboard
npm install   # first time only
npm run dev
```

Opens at http://localhost:5173. The dashboard shows:

- **Equity curve** — portfolio value over time
- **Open positions** — ticker, shares, avg cost, current price, P&L
- **Trade history** — timestamped log of all buys and sells
- **Start/Stop toggle** — control the trading agent

Data is read from `trades.json` in the project root, which the trading agent updates after every trade execution. The dashboard polls every 5 seconds for updates.

## Project Structure

```
finrl-trading-agent/
├── .env                          # API keys (gitignored)
├── trades.json                   # Live trade data for dashboard
├── dashboard/                    # React monitoring dashboard
│   └── src/Dashboard.jsx
├── src/
│   ├── main.py                   # CLI entry point
│   ├── config/settings.py        # Centralized config (reads .env)
│   ├── strategies/
│   │   ├── adaptive_rotation/    # Core strategy engine
│   │   ├── run_adaptive_rotation_strategy.py  # Backtest runner
│   │   └── AdaptiveRotationConf_v1.2.2.yaml   # Strategy config
│   ├── trading/
│   │   ├── alpaca_manager.py     # Alpaca API integration
│   │   ├── trade_executor.py     # Order execution + trades.json logging
│   │   └── trades_logger.py      # Dashboard data writer
│   └── data/                     # Data fetching and processing
├── data/
│   ├── fmp_daily/                # Per-symbol daily CSV files
│   └── finrl_trading.db          # SQLite price database
└── venv/                         # Python virtual environment
```

## Strategy Overview

The **Adaptive Multi-Asset Rotation Strategy** rotates capital across 4 asset groups (Growth/Tech, Cyclical, Real Assets, Defensive) based on market regime detection:

- **Risk-On**: Full allocation, top 2 groups
- **Neutral**: Reduced allocation, 70% group cap
- **Risk-Off**: Conservative, 50% group cap, 30% cash floor
- **Fast Risk-Off**: Daily shock detection, immediate 50% cash

Weekly rebalance on Fridays with daily stop-loss and fast risk-off monitoring.
