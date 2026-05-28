#!/usr/bin/env python3
"""
FinRL Daily Trading Agent
=========================
Runs automatically via cron/launchd every trading day.

- Monday–Thursday: risk monitoring only (stop-loss + fast risk-off checks)
- Friday: full strategy rebalance via Adaptive Rotation

Usage:
    python run_agent.py              # auto-detect day
    python run_agent.py --rebalance  # force full rebalance
    python run_agent.py --dry-run    # preview without placing orders
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime, date
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

load_dotenv(PROJECT_ROOT / ".env")

import requests
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_ROOT / "logs" / "agent.log"),
    ],
)
log = logging.getLogger("finrl-agent")

TRADES_FILE = PROJECT_ROOT / "trades.json"


def get_alpaca_headers():
    return {
        "APCA-API-KEY-ID": os.getenv("APCA_API_KEY"),
        "APCA-API-SECRET-KEY": os.getenv("APCA_API_SECRET"),
    }


def get_base_url():
    return os.getenv("APCA_BASE_URL", "https://paper-api.alpaca.markets")


def is_market_open():
    r = requests.get(f"{get_base_url()}/v2/clock", headers=get_alpaca_headers())
    clock = r.json()
    return clock.get("is_open", False)


def get_account():
    r = requests.get(f"{get_base_url()}/v2/account", headers=get_alpaca_headers())
    r.raise_for_status()
    return r.json()


def get_positions():
    r = requests.get(f"{get_base_url()}/v2/positions", headers=get_alpaca_headers())
    r.raise_for_status()
    return r.json()


def place_order(symbol, qty, side, dry_run=False):
    order = {
        "symbol": symbol,
        "qty": str(abs(qty)),
        "side": side,
        "type": "market",
        "time_in_force": "day",
    }
    if dry_run:
        log.info(f"  [DRY RUN] {side.upper()} {abs(qty)} {symbol}")
        return {"symbol": symbol, "side": side, "qty": qty, "status": "dry_run"}

    r = requests.post(
        f"{get_base_url()}/v2/orders",
        headers=get_alpaca_headers(),
        json=order,
    )
    r.raise_for_status()
    result = r.json()
    log.info(f"  ORDER: {side.upper()} {abs(qty)} {symbol} → {result['status']}")
    return result


def run_strategy():
    """Run the Adaptive Rotation strategy and return target weights."""
    from strategies.adaptive_rotation import AdaptiveRotationEngine
    from strategies.adaptive_rotation.data_preprocessor import DataPreprocessor
    from strategies.adaptive_rotation.config_loader import load_config

    config_path = str(PROJECT_ROOT / "src" / "strategies" / "AdaptiveRotationConf_v1.2.2.yaml")
    config = load_config(config_path)
    preprocessor = DataPreprocessor(config)
    preprocessor.load_and_prepare()

    engine = AdaptiveRotationEngine(config=config_path, data_preprocessor=preprocessor)

    today = date.today().isoformat()
    price_data = preprocessor.get_data_as_of(today)
    price_data = {sym: df["close"] for sym, df in price_data.items()}

    weights, audit = engine.run(price_data=price_data, as_of_date=today, mode="live")

    target = {}
    for sym, w in weights.weights.items():
        if w > 0.001:
            target[sym] = w

    log.info(f"Strategy output: regime={weights.regime_state}, "
             f"{len(target)} assets, invested={weights.get_invested_weight():.1%}")
    return target, weights.regime_state


def check_risk_triggers():
    """Check stop-loss and fast risk-off on current positions."""
    positions = get_positions()
    alerts = []

    for p in positions:
        sym = p["symbol"]
        entry = float(p["avg_entry_price"])
        current = float(p["current_price"])
        pnl_pct = (current - entry) / entry

        if pnl_pct <= -0.05:
            alerts.append({"symbol": sym, "trigger": "absolute_stop", "pnl_pct": pnl_pct})
            log.warning(f"  STOP-LOSS triggered: {sym} at {pnl_pct:.1%}")

        if float(p.get("unrealized_plpc", 0)) <= -0.10:
            alerts.append({"symbol": sym, "trigger": "trailing_stop", "pnl_pct": pnl_pct})
            log.warning(f"  TRAILING STOP triggered: {sym}")

    return alerts


def rebalance_to_weights(target_weights, dry_run=False):
    """Rebalance portfolio to match target weights."""
    acct = get_account()
    equity = float(acct["equity"])
    positions = get_positions()

    current_holdings = {}
    for p in positions:
        current_holdings[p["symbol"]] = {
            "qty": float(p["qty"]),
            "market_value": float(p["market_value"]),
            "current_price": float(p["current_price"]),
        }

    orders_placed = []

    # Sell positions not in target or overweight
    for sym, holding in current_holdings.items():
        target_w = target_weights.get(sym, 0)
        target_value = equity * target_w
        current_value = holding["market_value"]
        diff = target_value - current_value

        if target_w == 0:
            log.info(f"  Closing {sym}: selling {holding['qty']} shares")
            result = place_order(sym, holding["qty"], "sell", dry_run)
            orders_placed.append(result)
        elif diff < -holding["current_price"]:
            shares_to_sell = int(abs(diff) / holding["current_price"])
            if shares_to_sell > 0:
                result = place_order(sym, shares_to_sell, "sell", dry_run)
                orders_placed.append(result)

    # Buy new or underweight positions
    for sym, weight in target_weights.items():
        target_value = equity * weight
        current_value = current_holdings.get(sym, {}).get("market_value", 0)
        diff = target_value - current_value

        if diff > 100:
            price = current_holdings.get(sym, {}).get("current_price")
            if not price:
                try:
                    r = requests.get(
                        f"{get_base_url()}/v2/stocks/{sym}/quotes/latest",
                        headers=get_alpaca_headers(),
                    )
                    price = float(r.json()["quote"]["ap"])
                except Exception:
                    log.warning(f"  Could not get price for {sym}, skipping")
                    continue

            shares_to_buy = int(diff / price)
            if shares_to_buy > 0:
                result = place_order(sym, shares_to_buy, "buy", dry_run)
                orders_placed.append(result)

    return orders_placed


def update_trades_json(orders, regime=None):
    """Update trades.json with latest state for the dashboard."""
    acct = get_account()
    positions = get_positions()

    if TRADES_FILE.exists():
        state = json.loads(TRADES_FILE.read_text())
    else:
        state = {"agent_running": True, "equity_curve": [], "positions": [], "trade_history": []}

    state["agent_running"] = True
    state["last_updated"] = datetime.now().isoformat()

    state["equity_curve"].append({
        "timestamp": datetime.now().isoformat(),
        "equity": round(float(acct["equity"]), 2),
        "cash": round(float(acct["cash"]), 2),
    })

    state["positions"] = [
        {
            "ticker": p["symbol"],
            "shares": float(p["qty"]),
            "avg_cost": round(float(p["avg_entry_price"]), 2),
            "current_price": round(float(p["current_price"]), 2),
            "pnl": round(float(p["unrealized_pl"]), 2),
        }
        for p in positions
    ]

    for o in orders:
        if isinstance(o, dict) and o.get("status") != "dry_run":
            state["trade_history"].append({
                "timestamp": datetime.now().isoformat(),
                "action": o.get("side", "unknown"),
                "ticker": o.get("symbol", "?"),
                "qty": float(o.get("qty", 0)),
                "price": round(float(o.get("filled_avg_price", 0)), 2),
            })

    TRADES_FILE.write_text(json.dumps(state, indent=2, default=str))
    log.info(f"Dashboard updated: equity=${float(acct['equity']):,.2f}, {len(positions)} positions")


def main():
    parser = argparse.ArgumentParser(description="FinRL Daily Trading Agent")
    parser.add_argument("--rebalance", action="store_true", help="Force full rebalance")
    parser.add_argument("--dry-run", action="store_true", help="Preview without placing orders")
    args = parser.parse_args()

    (PROJECT_ROOT / "logs").mkdir(exist_ok=True)

    log.info("=" * 50)
    log.info("FinRL Trading Agent starting")
    log.info(f"Date: {date.today()}, Day: {date.today().strftime('%A')}")

    try:
        acct = get_account()
        log.info(f"Account connected: equity=${float(acct['equity']):,.2f}")
    except Exception as e:
        log.error(f"Cannot connect to Alpaca: {e}")
        sys.exit(1)

    if not is_market_open():
        log.info("Market is closed. Logging snapshot and exiting.")
        update_trades_json([])
        return

    is_friday = date.today().weekday() == 4
    do_rebalance = is_friday or args.rebalance

    orders = []

    # Step 1: Always check risk triggers
    log.info("Checking risk triggers...")
    alerts = check_risk_triggers()

    if alerts:
        log.warning(f"{len(alerts)} stop-loss triggers detected")
        for alert in alerts:
            result = place_order(alert["symbol"], 0, "sell", args.dry_run)
            # Sell full position for stopped symbols
            for p in get_positions():
                if p["symbol"] == alert["symbol"]:
                    result = place_order(alert["symbol"], float(p["qty"]), "sell", args.dry_run)
                    orders.append(result)
                    break

    # Step 2: Friday = full rebalance
    if do_rebalance:
        log.info("Running full strategy rebalance...")
        try:
            target_weights, regime = run_strategy()
            rebalance_orders = rebalance_to_weights(target_weights, args.dry_run)
            orders.extend(rebalance_orders)
            log.info(f"Rebalance complete: {len(rebalance_orders)} orders, regime={regime}")
        except Exception as e:
            log.error(f"Strategy execution failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        log.info(f"Not Friday — risk monitoring only. Next rebalance: Friday.")

    # Step 3: Update dashboard
    update_trades_json(orders)
    log.info(f"Agent finished. Orders: {len(orders)}")


if __name__ == "__main__":
    main()
