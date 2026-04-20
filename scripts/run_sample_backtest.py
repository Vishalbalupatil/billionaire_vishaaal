"""Run a sample backtest on synthetic OHLCV and print a summary report.

Usage:
    python scripts/run_sample_backtest.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from billionaire.backtest import BacktestEngine  # noqa: E402
from billionaire.logging_setup import setup_logging  # noqa: E402
from billionaire.models import Exchange, Instrument, Segment  # noqa: E402
from billionaire.strategy.examples import EXAMPLE_STRATEGIES  # noqa: E402
from billionaire.strategy.signal_engine import SignalEngine  # noqa: E402


def main() -> int:
    setup_logging()
    engine = SignalEngine([cls() for cls in EXAMPLE_STRATEGIES])
    bt = BacktestEngine(engine, warmup_bars=60, confidence_threshold=0.45, qty=1)
    ohlcv = bt.synthetic_ohlcv(n=1500, seed=42)
    instrument = Instrument(
        instrument_token=256265,
        tradingsymbol="NIFTY_SIM",
        exchange=Exchange.NSE,
        segment=Segment.INDEX,
    )
    result = bt.run(instrument=instrument, timeframe="5m", ohlcv=ohlcv)
    summary = {
        "trades": result.metrics.trades if result.metrics else 0,
        "win_rate": result.metrics.win_rate if result.metrics else 0,
        "total_pnl": result.metrics.total_pnl if result.metrics else 0,
        "max_drawdown": result.metrics.max_drawdown if result.metrics else 0,
        "profit_factor": result.metrics.profit_factor if result.metrics else 0,
        "expectancy": result.metrics.expectancy if result.metrics else 0,
        "per_strategy": {k: v.__dict__ for k, v in result.per_strategy.items()},
    }
    out = ROOT / "data" / "sample_backtest_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result.to_dict(), indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))
    print(f"\nFull report written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
