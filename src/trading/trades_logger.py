"""
Trades Logger — writes trade activity to trades.json for the monitoring dashboard.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

TRADES_FILE = Path(__file__).parent.parent.parent / "trades.json"


def _read_state() -> Dict[str, Any]:
    if TRADES_FILE.exists():
        try:
            return json.loads(TRADES_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "agent_running": False,
        "last_updated": None,
        "equity_curve": [],
        "positions": [],
        "trade_history": [],
    }


def _write_state(state: Dict[str, Any]):
    state["last_updated"] = datetime.now().isoformat()
    TRADES_FILE.write_text(json.dumps(state, indent=2, default=str))


def set_agent_running(running: bool):
    state = _read_state()
    state["agent_running"] = running
    _write_state(state)


def log_equity(equity: float, cash: float, timestamp: Optional[str] = None):
    state = _read_state()
    state["equity_curve"].append({
        "timestamp": timestamp or datetime.now().isoformat(),
        "equity": round(equity, 2),
        "cash": round(cash, 2),
    })
    _write_state(state)


def log_positions(positions: List[Dict[str, Any]]):
    state = _read_state()
    state["positions"] = positions
    _write_state(state)


def log_trade(action: str, ticker: str, qty: float, price: float,
              timestamp: Optional[str] = None):
    state = _read_state()
    state["trade_history"].append({
        "timestamp": timestamp or datetime.now().isoformat(),
        "action": action,
        "ticker": ticker,
        "qty": round(qty, 4),
        "price": round(price, 2),
    })
    if len(state["trade_history"]) > 500:
        state["trade_history"] = state["trade_history"][-500:]
    _write_state(state)


def log_execution_result(execution_result, portfolio_state: Optional[Dict] = None):
    """Log a full ExecutionResult from TradeExecutor."""
    state = _read_state()

    for order in execution_result.orders_placed:
        od = order if isinstance(order, dict) else order.__dict__
        state["trade_history"].append({
            "timestamp": execution_result.execution_time.isoformat()
            if hasattr(execution_result.execution_time, "isoformat")
            else str(execution_result.execution_time),
            "action": od.get("side", "unknown"),
            "ticker": od.get("symbol", "?"),
            "qty": round(float(od.get("quantity", od.get("filled_qty", 0))), 4),
            "price": round(float(od.get("filled_avg_price", od.get("price", 0))), 2),
        })

    if portfolio_state:
        equity = float(portfolio_state.get("equity", 0))
        cash = float(portfolio_state.get("cash", 0))
        state["equity_curve"].append({
            "timestamp": datetime.now().isoformat(),
            "equity": round(equity, 2),
            "cash": round(cash, 2),
        })

        positions = []
        for pos in portfolio_state.get("positions", []):
            p = pos if isinstance(pos, dict) else pos.__dict__
            positions.append({
                "ticker": p.get("symbol", "?"),
                "shares": round(float(p.get("qty", 0)), 4),
                "avg_cost": round(float(p.get("avg_entry_price", 0)), 2),
                "current_price": round(float(p.get("current_price", 0)), 2),
                "pnl": round(float(p.get("unrealized_pl", 0)), 2),
            })
        state["positions"] = positions

    if len(state["trade_history"]) > 500:
        state["trade_history"] = state["trade_history"][-500:]

    _write_state(state)
