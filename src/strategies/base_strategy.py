from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional
import pandas as pd

@dataclass
class StrategyResult:
    strategy_name: str
    weights: pd.DataFrame
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class StrategyConfig:
    name: str = "BaseStrategy"

class BaseStrategy:
    """Minimal base strategy interface."""

    def __init__(self, config: StrategyConfig):
        self.config = config

    def generate_weights(self, data: Dict[str, pd.DataFrame], target_date: Optional[str] = None) -> StrategyResult:
        raise NotImplementedError("generate_weights must be implemented by subclasses")


class EqualWeightStrategy(BaseStrategy):
    """Equal-weight allocation across all provided assets."""

    def generate_weights(self, data: Dict[str, pd.DataFrame], target_date: Optional[str] = None) -> StrategyResult:
        symbols = list(data.keys())
        n = len(symbols) if symbols else 1
        weight = 1.0 / n
        weights_df = pd.DataFrame({"symbol": symbols, "weight": [weight] * len(symbols)})
        return StrategyResult(strategy_name=self.config.name, weights=weights_df)


_STRATEGY_REGISTRY: Dict[str, type] = {
    "equal_weight": EqualWeightStrategy,
}


def create_strategy(strategy_type: str, config: StrategyConfig) -> BaseStrategy:
    """Factory function to create a strategy by name."""
    cls = _STRATEGY_REGISTRY.get(strategy_type.lower(), EqualWeightStrategy)
    return cls(config)
