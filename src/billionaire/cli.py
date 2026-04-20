"""Command-line entrypoints."""

from __future__ import annotations

import argparse
import json
import sys

from billionaire.backtest import BacktestEngine
from billionaire.logging_setup import setup_logging
from billionaire.models import Exchange, Instrument, Segment
from billionaire.runtime import get_runtime
from billionaire.strategy.examples import EXAMPLE_STRATEGIES
from billionaire.strategy.signal_engine import SignalEngine


def _cmd_status(_: argparse.Namespace) -> int:
    r = get_runtime()
    print(
        json.dumps(
            {
                "mode": r.settings.app_mode.value,
                "live_trading_enabled": r.settings.live_trading_enabled,
                "risk": r.risk.status(),
            },
            indent=2,
        )
    )
    return 0


def _cmd_backtest(args: argparse.Namespace) -> int:
    engine = SignalEngine([cls() for cls in EXAMPLE_STRATEGIES])
    bt = BacktestEngine(engine, warmup_bars=60, confidence_threshold=args.confidence)
    ohlcv = bt.synthetic_ohlcv(n=args.bars, seed=args.seed)
    inst = Instrument(
        instrument_token=999999,
        tradingsymbol=args.symbol,
        exchange=Exchange.NSE,
        segment=Segment.INDEX,
    )
    result = bt.run(instrument=inst, timeframe="5m", ohlcv=ohlcv)
    print(json.dumps(result.to_dict(), indent=2, default=str))
    return 0


def _cmd_serve(_: argparse.Namespace) -> int:
    import uvicorn

    s = get_runtime().settings
    uvicorn.run("billionaire.app:app", host=s.api_host, port=s.api_port, reload=False)
    return 0


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    parser = argparse.ArgumentParser("billionaire")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Print runtime status").set_defaults(func=_cmd_status)

    bt = sub.add_parser("backtest", help="Run sample backtest with synthetic data")
    bt.add_argument("--symbol", default="NIFTY")
    bt.add_argument("--bars", type=int, default=500)
    bt.add_argument("--seed", type=int, default=7)
    bt.add_argument("--confidence", type=float, default=0.45)
    bt.set_defaults(func=_cmd_backtest)

    sub.add_parser("serve", help="Run the FastAPI server").set_defaults(func=_cmd_serve)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
