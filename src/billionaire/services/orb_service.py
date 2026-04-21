"""Application-layer orchestration for the ORB strategy.

Two responsibilities:

* **Backtest artefact lifecycle** — load a previously-run backtest JSON
  from disk (produced by ``python -m billionaire.cli backtest-orb``), or,
  when absent, generate a deterministic synthetic-data artefact so the UI
  has something to render. Everything is cached in-process after first
  load — backtests are not cheap and we don't want to re-run per request.
* **Today's ORB state** — build a live snapshot using whatever candle
  history the runtime currently holds (from ``CandleBuilder`` in live
  mode, or synthetic closes when offline/pre-market), attach deterministic
  scenario projections, and evaluate the probabilistic ML-lite model
  trained on the most recent backtest's trade log.

The "today" endpoint is deliberately forgiving: it will return *something*
useful even when neither a backtest artefact nor live data is available.
Degraded responses carry a ``source`` field the UI can show.
"""

from __future__ import annotations

import json
import logging
import random
import threading
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from billionaire.backtest.orb_backtest import (
    ORBBacktestResult,
    bars_from_cache,
    run_backtest,
)
from billionaire.marketdata.historical_cache import HistoricalCache
from billionaire.strategy.options_pricing import (
    BSInputs,
    atm_strike,
    current_month_expiry,
    price_call,
    price_put,
    vix_to_sigma,
    years_to_expiry,
)
from billionaire.strategy.orb import Bar, find_first_break, find_opening_range
from billionaire.strategy.orb_probability import (
    CLASS_NAMES,
    LogisticModel,
    build_features,
    fit,
)

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
DEFAULT_ARTEFACT_PATH = Path("data/artifacts/orb_backtest.json")
DEFAULT_CACHE_PATH = Path("data/historical_bars.db")


# ---------------------------------------------------------------------------
# Backtest artefact loading / synthesis
# ---------------------------------------------------------------------------


def _synth_backtest(days: int = 250, seed: int = 7) -> dict[str, Any]:
    """Generate a deterministic fake ``ORBBacktestResult.to_dict()`` payload.

    Useful when the user hasn't yet run ``backtest-orb`` (no Kite token, no
    historical cache). Keeps the dashboard inhabitable on first boot. The
    generated distribution is chosen to look "plausible" rather than
    accurate — it advertises itself as ``data_source: "synthetic"`` so no
    one mistakes it for real data.
    """
    rng = random.Random(seed)
    spot = 24_800.0
    trades: list[dict[str, Any]] = []
    equity_combined: list[dict[str, Any]] = []
    equity_fut: list[dict[str, Any]] = []
    equity_opt: list[dict[str, Any]] = []
    start = date.today() - timedelta(days=int(days * 1.4))
    cum_c = 0.0
    cum_f = 0.0
    cum_o = 0.0
    trade_ix = 0
    for i in range(days):
        d = start + timedelta(days=i)
        # Skip weekends for realism
        if d.weekday() >= 5:
            continue

        # ~30% no-trade days
        roll = rng.random()
        if roll < 0.30:
            equity_combined.append({"date": d.isoformat(), "equity": cum_c})
            equity_fut.append({"date": d.isoformat(), "equity": cum_f})
            equity_opt.append({"date": d.isoformat(), "equity": cum_o})
            continue

        side = "LONG" if rng.random() < 0.52 else "SHORT"
        or_width = rng.uniform(30, 90)
        risk_points = or_width
        r_mult = rng.choices(
            population=[-1.0, 2.0, rng.uniform(-0.3, 1.5)],
            weights=[0.45, 0.35, 0.20],
        )[0]
        fut_points = r_mult * risk_points
        fut_rupees = fut_points * 75
        opt_rupees = fut_rupees * rng.uniform(0.25, 0.55) * (1 if r_mult > 0 else -1)
        combined = fut_rupees + opt_rupees - 160  # fees
        cum_f += fut_rupees - 80
        cum_o += opt_rupees - 80
        cum_c += combined

        or_low = spot + rng.uniform(-80, 80)
        or_high = or_low + or_width
        if side == "LONG":
            entry = or_high
            stop = or_low
        else:
            entry = or_low
            stop = or_high

        trades.append({
            "date": d.isoformat(),
            "side": side,
            "or_high": round(or_high, 2),
            "or_low": round(or_low, 2),
            "or_ts": datetime.combine(d, time(9, 15)).isoformat(),
            "entry_ts": datetime.combine(d, time(9, 25)).isoformat(),
            "entry_price": round(entry, 2),
            "stop_price": round(stop, 2),
            "target_price": round(
                entry + 2.0 * risk_points * (1 if side == "LONG" else -1), 2
            ),
            "exit_ts": datetime.combine(d, time(11, 30)).isoformat(),
            "exit_price": round(entry + fut_points, 2),
            "exit_reason": "target" if r_mult >= 1.5 else ("stop" if r_mult <= -0.9 else "eod"),
            "futures_pnl_points": round(fut_points, 2),
            "futures_pnl_pct": round(fut_points / entry * 100, 4),
            "futures_pnl_rupees": round(fut_rupees, 2),
            "option_type": "CE" if side == "LONG" else "PE",
            "option_strike": int(round(spot / 50) * 50),
            "option_entry_premium": round(rng.uniform(80, 140), 2),
            "option_exit_premium": round(rng.uniform(60, 180), 2),
            "option_pnl_points": round(opt_rupees / 75, 2),
            "option_pnl_rupees": round(opt_rupees, 2),
            "vix_at_entry": round(rng.uniform(10.5, 18.5), 2),
            "days_to_expiry": round(rng.uniform(0.01, 0.09), 4),
            "combined_pnl_rupees": round(combined, 2),
            "r_multiple": round(r_mult, 3),
            "bars_held": rng.randint(3, 40),
        })
        trade_ix += 1
        equity_combined.append({"date": d.isoformat(), "equity": round(cum_c, 2)})
        equity_fut.append({"date": d.isoformat(), "equity": round(cum_f, 2)})
        equity_opt.append({"date": d.isoformat(), "equity": round(cum_o, 2)})
        spot += rng.uniform(-60, 60)

    wins = sum(1 for t in trades if t["combined_pnl_rupees"] > 0)
    losses = sum(1 for t in trades if t["combined_pnl_rupees"] <= 0)
    no_trade = sum(
        1 for e in equity_combined if not any(t["date"] == e["date"] for t in trades)
    )
    total_pnl = sum(t["combined_pnl_rupees"] for t in trades)
    fut_pnl = sum(t["futures_pnl_rupees"] for t in trades)
    opt_pnl = sum(t["option_pnl_rupees"] for t in trades)
    best = max((t["combined_pnl_rupees"] for t in trades), default=0.0)
    worst = min((t["combined_pnl_rupees"] for t in trades), default=0.0)
    avg_r = sum(t["r_multiple"] for t in trades) / len(trades) if trades else 0.0

    # Max drawdown from equity curve
    peak = -float("inf")
    max_dd = 0.0
    for e in equity_combined:
        if e["equity"] > peak:
            peak = e["equity"]
        dd = peak - e["equity"]
        if dd > max_dd:
            max_dd = dd

    return {
        "trades": trades,
        "equity_curve_combined": equity_combined,
        "equity_curve_futures": equity_fut,
        "equity_curve_options": equity_opt,
        "metrics": {
            "total_trades": len(trades),
            "wins": wins,
            "losses": losses,
            "no_trade_days": no_trade,
            "win_rate_pct": round(100 * wins / len(trades), 2) if trades else 0.0,
            "avg_r_multiple": round(avg_r, 3),
            "best_trade_rupees": round(best, 2),
            "worst_trade_rupees": round(worst, 2),
            "total_pnl_rupees": round(total_pnl, 2),
            "futures_pnl_rupees": round(fut_pnl, 2),
            "options_pnl_rupees": round(opt_pnl, 2),
            "max_drawdown_rupees": round(max_dd, 2),
            "sharpe_ratio": 0.0,
        },
        "params": {
            "rr": 2.0, "square_off_time": "15:15", "futures_lot_size": 75,
            "options_lot_size": 75, "risk_free_rate": 0.075,
            "dividend_yield": 0.013, "fees_per_leg_rupees": 40.0,
        },
        "data_source": "synthetic",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def load_backtest_artefact(path: Path = DEFAULT_ARTEFACT_PATH) -> dict[str, Any]:
    """Load the JSON produced by ``backtest-orb``; synthesise if absent."""
    if path.exists():
        try:
            with path.open() as f:
                payload = json.load(f)
            payload.setdefault("data_source", "live-cache")
            return payload
        except (OSError, json.JSONDecodeError) as e:
            log.warning("backtest artefact unreadable (%s); falling back to synthetic", e)
    return _synth_backtest()


def save_backtest_artefact(result: ORBBacktestResult, path: Path = DEFAULT_ARTEFACT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = result.to_dict()
    payload["data_source"] = "live-cache"
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    with path.open("w") as f:
        json.dump(payload, f, indent=2, default=str)
    return path


# ---------------------------------------------------------------------------
# Probability model
# ---------------------------------------------------------------------------


@dataclass
class ProbabilityContext:
    model: LogisticModel | None
    n_samples: int
    reason: str  # human-readable note ("ok" / "insufficient_data" / etc.)


def _trade_rows_to_dataset(
    trades: list[dict[str, Any]]
) -> tuple[list[list[float]], list[str]]:
    """Turn backtest trades into (X, y) for the logistic regression.

    We only use features derivable at 09:20 IST (pre-trade): OR width, gap
    vs previous day's close, VIX, prev-day return, day of week. Any feature
    peeking at post-09:20 data would leak and inflate accuracy.
    """
    features: list[list[float]] = []
    labels: list[str] = []
    # Build a fast prev-close lookup by iterating once in order.
    sorted_trades = sorted(trades, key=lambda t: t["date"])
    for i, t in enumerate(sorted_trades):
        if i == 0:
            continue  # need previous day's close
        prev = sorted_trades[i - 1]
        try:
            or_high = float(t["or_high"])
            or_low = float(t["or_low"])
            prev_close = float(prev["exit_price"])
            today_open = float(t["or_low"])  # 09:15 open ≈ OR-low as proxy
            vix = float(t.get("vix_at_entry") or 15.0)
            prev_ret = (
                (float(prev["exit_price"]) - float(prev["entry_price"]))
                / max(float(prev["entry_price"]), 1e-9) * 100.0
            )
            weekday = datetime.fromisoformat(t["date"]).weekday()
        except (KeyError, ValueError, TypeError):
            continue
        features.append(build_features(
            or_high=or_high, or_low=or_low, prev_close=prev_close,
            today_open=today_open, vix_value=vix,
            prev_day_return_pct=prev_ret, weekday=weekday,
        ))
        labels.append(t["side"])  # LONG | SHORT
    return features, labels


def train_probability_model(
    artefact: dict[str, Any], min_samples: int = 50
) -> ProbabilityContext:
    trades = artefact.get("trades", [])
    features, labels = _trade_rows_to_dataset(trades)
    if len(features) < min_samples:
        return ProbabilityContext(None, len(features), "insufficient_data")
    # Use all three classes so the output is well-defined even if training
    # data is skewed (rarely produces NONE from backtest trades but we keep
    # the column for symmetry with the UI).
    try:
        m = fit(
            features, labels, epochs=400, learning_rate=0.1, l2=0.001,
            classes=sorted(set(labels)),
        )
    except ValueError as e:
        return ProbabilityContext(None, len(features), f"fit_error: {e}")
    return ProbabilityContext(m, len(features), "ok")


# ---------------------------------------------------------------------------
# Today's ORB snapshot
# ---------------------------------------------------------------------------


@dataclass
class TodaysORB:
    trading_date: str
    or_formed: bool
    or_high: float | None
    or_low: float | None
    or_ts: str | None
    spot: float | None
    vix: float | None
    now_ts: str  # IST ISO
    bars_seen: int
    source: str  # "live" | "cache" | "synthetic"

    def to_dict(self) -> dict[str, Any]:
        return {
            "trading_date": self.trading_date,
            "or_formed": self.or_formed,
            "or_high": self.or_high,
            "or_low": self.or_low,
            "or_ts": self.or_ts,
            "spot": self.spot,
            "vix": self.vix,
            "now_ts": self.now_ts,
            "bars_seen": self.bars_seen,
            "source": self.source,
        }


def compute_deterministic_scenarios(
    *, or_high: float, or_low: float, spot: float, vix_value: float, rr: float = 2.0,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Given the OR, project the two canonical outcomes (long break / short
    break) with their futures P&L and BS-priced option premium deltas.

    Pure function — no I/O. Symmetric output helps the UI render both
    sides side-by-side."""
    now_ist = now or datetime.now(IST).replace(tzinfo=None)
    expiry = current_month_expiry(now_ist)
    tte = years_to_expiry(now_ist, expiry)
    sigma = vix_to_sigma(vix_value)
    strike = atm_strike(spot)

    risk = or_high - or_low
    long_target = or_high + rr * risk
    long_stop = or_low
    short_target = or_low - rr * risk
    short_stop = or_high

    # Price ATM call + put at current spot.
    inp_now = BSInputs(S=spot, K=strike, T=tte, sigma=sigma)
    call_now = price_call(inp_now).premium
    put_now = price_put(inp_now).premium

    # Price the same options if spot moves to each scenario exit.
    inp_long_exit = BSInputs(S=long_target, K=strike, T=tte, sigma=sigma)
    inp_short_exit = BSInputs(S=short_target, K=strike, T=tte, sigma=sigma)
    call_long_exit = price_call(inp_long_exit).premium
    put_short_exit = price_put(inp_short_exit).premium

    return {
        "now_ts": now_ist.isoformat(),
        "or_high": or_high,
        "or_low": or_low,
        "spot": spot,
        "vix": vix_value,
        "atm_strike": strike,
        "rr": rr,
        "call_now_premium": round(call_now, 2),
        "put_now_premium": round(put_now, 2),
        "long_scenario": {
            "entry": or_high, "stop": long_stop, "target": long_target,
            "futures_pnl_rupees": round((long_target - or_high) * 75, 2),
            "option_entry_premium": round(call_now, 2),
            "option_target_premium": round(call_long_exit, 2),
            "option_pnl_rupees": round((call_long_exit - call_now) * 75, 2),
        },
        "short_scenario": {
            "entry": or_low, "stop": short_stop, "target": short_target,
            "futures_pnl_rupees": round((or_low - short_target) * 75, 2),
            "option_entry_premium": round(put_now, 2),
            "option_target_premium": round(put_short_exit, 2),
            "option_pnl_rupees": round((put_short_exit - put_now) * 75, 2),
        },
    }


def evaluate_probability(
    ctx: ProbabilityContext, *,
    or_high: float, or_low: float, prev_close: float, today_open: float,
    vix_value: float, prev_day_return_pct: float, weekday: int,
) -> dict[str, float]:
    """Evaluate the trained model; returns uniform 1/3 probs when untrained."""
    if ctx.model is None:
        return {k: 1.0 / len(CLASS_NAMES) for k in CLASS_NAMES}
    row = build_features(
        or_high=or_high, or_low=or_low, prev_close=prev_close,
        today_open=today_open, vix_value=vix_value,
        prev_day_return_pct=prev_day_return_pct, weekday=weekday,
    )
    probs = ctx.model.predict_proba(row)
    # Backfill any missing class with 0 so the UI can always iterate CLASS_NAMES.
    return {k: float(probs.get(k, 0.0)) for k in CLASS_NAMES}


# ---------------------------------------------------------------------------
# Singleton service state
# ---------------------------------------------------------------------------


class ORBService:
    """In-memory cache of the latest backtest + trained probability model.

    Thread-safe-enough for FastAPI: we only ever rebuild on explicit
    refresh, and reads are lock-free since dict reads are atomic in CPython.
    """

    def __init__(self, artefact_path: Path = DEFAULT_ARTEFACT_PATH):
        self._artefact_path = artefact_path
        self._lock = threading.RLock()
        self._artefact: dict[str, Any] | None = None
        self._prob: ProbabilityContext | None = None

    def _ensure_loaded(self) -> None:
        with self._lock:
            if self._artefact is None:
                self._artefact = load_backtest_artefact(self._artefact_path)
                self._prob = train_probability_model(self._artefact)

    def refresh(self) -> None:
        with self._lock:
            self._artefact = load_backtest_artefact(self._artefact_path)
            self._prob = train_probability_model(self._artefact)

    def artefact(self) -> dict[str, Any]:
        self._ensure_loaded()
        assert self._artefact is not None
        return self._artefact

    def probability_ctx(self) -> ProbabilityContext:
        self._ensure_loaded()
        assert self._prob is not None
        return self._prob


_orb_service: ORBService | None = None
_svc_lock = threading.RLock()


def get_orb_service() -> ORBService:
    global _orb_service
    with _svc_lock:
        if _orb_service is None:
            _orb_service = ORBService()
        return _orb_service


# ---------------------------------------------------------------------------
# Live / cached "today" snapshot helpers
# ---------------------------------------------------------------------------


def today_from_cache(
    cache_path: Path = DEFAULT_CACHE_PATH,
    *,
    futures_token: int | None = None,
    spot_token: int = 256265,  # NIFTY 50 index
    vix_token: int = 264969,
    as_of: datetime | None = None,
) -> TodaysORB | None:
    """Best-effort reconstruct today's ORB from the local SQLite cache.

    Returns ``None`` if the cache file is missing or contains no bars for
    today. Used as the primary data source for ``/api/forecast/orb-today``
    — live tick data would be more precise but this works even when the
    backend is stopped, and we only need the first 5m candle anyway.
    """
    if not cache_path.exists():
        return None
    now = as_of or datetime.now(IST).replace(tzinfo=None)
    today = now.date()
    # Pull the full trading-session window for today's date.
    from_ts = datetime.combine(today, time(9, 15))
    to_ts = datetime.combine(today, time(15, 30))
    try:
        cache = HistoricalCache(cache_path)
    except Exception as e:  # pragma: no cover — defensive, shouldn't happen
        log.warning("failed to open historical cache: %s", e)
        return None
    try:
        token = futures_token or spot_token
        bars = bars_from_cache(cache, token, "5m", from_ts, to_ts)
        if not bars:
            return None
        orr = find_opening_range(bars)
        spot_bar = bars[-1] if bars else None
        vix_bars = bars_from_cache(cache, vix_token, "5m", from_ts, to_ts)
        vix_val = vix_bars[-1].close if vix_bars else None
        return TodaysORB(
            trading_date=today.isoformat(),
            or_formed=orr is not None,
            or_high=orr.high if orr else None,
            or_low=orr.low if orr else None,
            or_ts=orr.ts.isoformat() if orr else None,
            spot=spot_bar.close if spot_bar else None,
            vix=vix_val,
            now_ts=now.isoformat(),
            bars_seen=len(bars),
            source="cache",
        )
    finally:
        cache.close()


def synth_today_snapshot(seed: int | None = None) -> tuple[TodaysORB, list[Bar]]:
    """Generate a plausible live-day snapshot for demos.

    Returned :class:`TodaysORB` carries ``source="synthetic"`` so the UI
    knows not to display real-money framing around the numbers.
    """
    rng = random.Random(seed or 42)
    now_ist = datetime.now(IST).replace(tzinfo=None)
    today = now_ist.date()
    spot = 24_800 + rng.uniform(-40, 40)
    width = rng.uniform(30, 80)
    or_low = spot - rng.uniform(5, width)
    or_high = or_low + width
    or_ts = datetime.combine(today, time(9, 15))
    bars: list[Bar] = [
        Bar(ts=or_ts, open=spot, high=or_high, low=or_low, close=(or_high + or_low) / 2)
    ]
    # Synthesize a few post-OR bars up to 'now' to drive any break detection.
    t = or_ts + timedelta(minutes=5)
    price = (or_high + or_low) / 2
    while t <= now_ist and t.time() <= time(15, 20):
        drift = rng.uniform(-or_low * 0.0008, or_low * 0.0008)
        o = price
        price = price + drift
        h = max(o, price) + rng.uniform(0, 5)
        lo = min(o, price) - rng.uniform(0, 5)
        bars.append(Bar(ts=t, open=o, high=h, low=lo, close=price))
        t += timedelta(minutes=5)
    return TodaysORB(
        trading_date=today.isoformat(),
        or_formed=True,
        or_high=or_high,
        or_low=or_low,
        or_ts=or_ts.isoformat(),
        spot=price,
        vix=rng.uniform(11.0, 17.0),
        now_ts=now_ist.isoformat(),
        bars_seen=len(bars),
        source="synthetic",
    ), bars


def current_break(bars: list[Bar]) -> dict[str, Any] | None:
    """If today's bars already triggered a break, return the break summary."""
    orr = find_opening_range(bars)
    if not orr or len(bars) < 2:
        return None
    br = find_first_break(orr, bars[1:], rr=2.0)
    if br is None:
        return None
    return {
        "side": br.side.value,
        "ts": br.ts.isoformat(),
        "entry_price": br.entry_price,
        "stop_price": br.stop_price,
        "target_price": br.target_price,
    }


# ---------------------------------------------------------------------------
# Entrypoint used by the CLI to run a full backtest against the cache
# ---------------------------------------------------------------------------


def run_and_persist_backtest(
    *,
    years: int,
    cache_path: Path,
    futures_token: int,
    spot_token: int = 256265,
    vix_token: int = 264969,
    rr: float = 2.0,
    artefact_path: Path = DEFAULT_ARTEFACT_PATH,
) -> tuple[ORBBacktestResult, Path]:
    """Run the ORB backtest against the local cache and persist the result.

    This does NOT call Kite — callers must pre-populate the cache with
    ``backfill_last_n_years`` or similar. Separating the fetch step from
    the compute step keeps tests offline and makes failure modes obvious.
    """
    cache = HistoricalCache(cache_path)
    try:
        to_ts = datetime.now(IST).replace(tzinfo=None)
        from_ts = to_ts - timedelta(days=int(years * 365.25))
        fut_bars = bars_from_cache(cache, futures_token, "5m", from_ts, to_ts)
        spot_bars = bars_from_cache(cache, spot_token, "5m", from_ts, to_ts)
        vix_bars = bars_from_cache(cache, vix_token, "5m", from_ts, to_ts)
    finally:
        cache.close()
    if not fut_bars:
        raise RuntimeError(
            f"historical cache has no futures bars for token {futures_token}; "
            "run the fetcher first"
        )
    result = run_backtest(
        futures_bars=fut_bars, spot_bars=spot_bars, vix_bars=vix_bars, rr=rr,
    )
    out = save_backtest_artefact(result, artefact_path)
    return result, out
