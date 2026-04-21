"""Command-line entrypoints."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from billionaire.backtest import BacktestEngine
from billionaire.logging_setup import setup_logging
from billionaire.models import Exchange, Instrument, Segment
from billionaire.runtime import get_runtime
from billionaire.services.orb_service import (
    DEFAULT_ARTEFACT_PATH,
    DEFAULT_CACHE_PATH,
    run_and_persist_backtest,
)
from billionaire.strategy.examples import EXAMPLE_STRATEGIES
from billionaire.strategy.signal_engine import SignalEngine

log = logging.getLogger(__name__)


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


def _cmd_backtest_orb(args: argparse.Namespace) -> int:
    """Pull Kite historical bars (if needed), run the ORB backtest, persist.

    The fetch step uses the live broker configured in ``.env`` — requires
    ``KITE_API_KEY`` / ``KITE_ACCESS_TOKEN`` with the historical-data add-on
    enabled. If ``--skip-fetch`` is passed we go straight to running the
    backtest against whatever is already cached locally.
    """
    from billionaire.marketdata.historical_cache import HistoricalCache
    from billionaire.marketdata.historical_fetcher import (
        INDIA_VIX_TOKEN,
        NIFTY50_INDEX_TOKEN,
        backfill_last_n_years,
        resolve_front_month_future_token,
    )

    cache_path = Path(args.cache_db)
    artefact_path = Path(args.artefact)
    years = int(args.years)

    futures_token = int(args.futures_token) if args.futures_token else 0
    if not args.skip_fetch:
        runtime = get_runtime()
        broker = runtime.live_broker
        if broker is None:
            print(
                "ERROR: no live broker configured. Set KITE_API_KEY + "
                "KITE_ACCESS_TOKEN in .env, or re-run with --skip-fetch to "
                "use already-cached bars.",
                file=sys.stderr,
            )
            return 2

        if not futures_token:
            # Lazily load instrument master to find the front-month future.
            instruments = runtime.instruments
            if instruments is None:
                print("ERROR: instrument master unavailable", file=sys.stderr)
                return 2
            # Ensure it's loaded; .load() is idempotent.
            try:
                instruments.load()  # type: ignore[attr-defined]
            except Exception as e:  # pragma: no cover — network dependent
                print(f"WARN: instrument master load failed: {e}", file=sys.stderr)
            try:
                futures_token = resolve_front_month_future_token(
                    instruments, underlying="NIFTY"
                )
            except (LookupError, AttributeError) as e:
                print(
                    f"ERROR: couldn't resolve NIFTY front-month futures token: "
                    f"{e}. Re-run with --futures-token <TOKEN>.",
                    file=sys.stderr,
                )
                return 2
            print(f"Resolved NIFTY front-month futures token = {futures_token}")

        cache = HistoricalCache(cache_path)
        try:
            print(
                f"Fetching {years}y of 5m bars for "
                f"[fut={futures_token}, spot={NIFTY50_INDEX_TOKEN}, "
                f"vix={INDIA_VIX_TOKEN}]…"
            )
            results = backfill_last_n_years(
                broker, cache,
                tokens=[futures_token, NIFTY50_INDEX_TOKEN, INDIA_VIX_TOKEN],
                timeframe="5m", years=years,
            )
            for r in results:
                print(
                    f"  token={r.token} chunks={r.chunks} bars_written={r.bars_written}"
                )
        finally:
            cache.close()
    else:
        if not futures_token:
            print(
                "ERROR: --skip-fetch requires --futures-token <TOKEN>",
                file=sys.stderr,
            )
            return 2

    print("Running ORB backtest…")
    result, out_path = run_and_persist_backtest(
        years=years,
        cache_path=cache_path,
        futures_token=futures_token,
        rr=float(args.rr),
        artefact_path=artefact_path,
    )
    print(f"  → {len(result.trades)} trades, "
          f"win_rate={result.metrics.win_rate_pct:.2f}%, "
          f"net_pnl=₹{result.metrics.total_pnl_rupees:,.0f}")
    print(f"Artefact written to {out_path}")
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

    ob = sub.add_parser(
        "backtest-orb",
        help="Pull Kite historical 5m bars, run ORB backtest, persist artefact.",
    )
    ob.add_argument("--years", type=int, default=2, help="years of history to pull")
    ob.add_argument(
        "--cache-db", default=str(DEFAULT_CACHE_PATH),
        help="SQLite cache path",
    )
    ob.add_argument(
        "--artefact", default=str(DEFAULT_ARTEFACT_PATH),
        help="where to write the backtest JSON",
    )
    ob.add_argument("--futures-token", default=None, help="NIFTY front-month futures token")
    ob.add_argument("--rr", type=float, default=2.0, help="risk-reward ratio")
    ob.add_argument(
        "--skip-fetch", action="store_true",
        help="skip the Kite REST pull and use whatever is already cached",
    )
    ob.set_defaults(func=_cmd_backtest_orb)

    sub.add_parser("serve", help="Run the FastAPI server").set_defaults(func=_cmd_serve)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
