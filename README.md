# Billionaire Vishaaal

> AI-assisted trading platform for Indian markets (Nifty, Bank Nifty, equity,
> futures, options) integrated with **Zerodha Kite Connect**.

**⚠️ This is a decision-support and execution tool. It is NOT financial advice.
No profits are guaranteed. No "100% accurate AI". Always paper-trade new
strategies. Live orders are locked behind an explicit unlock phrase.**

---

## Highlights

- **Modular, broker-agnostic architecture** — paper and live brokers share the
  same `BrokerClient` interface.
- **Typed domain models** (Pydantic) end-to-end; audit-grade JSON logs.
- **Live market pipeline**: Kite WebSocket → `Tick` → multi-timeframe
  `CandleBuilder` → `IndicatorEngine` → `SignalEngine` (explainable scoring)
  → `RiskManager` → `OrderManager`.
- **Analysis / Paper / Live** modes with hard safeguards (kill switch, daily
  loss lock, cooldown after losses, per-trade risk sizing, square-off).
- **Options analytics**: PCR, max pain, call/put walls, Black-Scholes IV +
  greeks.
- **Backtest engine** reusing the exact live pipeline + a sample report.
- **Futuristic dark dashboard** (React + Vite + TypeScript, glassmorphism,
  neon accents).
- **Alert abstraction** with console, Telegram and SMTP channels.

---

## Project Layout

```
billionaire_vishaaal/
├── src/billionaire/
│   ├── app.py                       FastAPI entry
│   ├── cli.py                       `billionaire` CLI
│   ├── runtime.py                   Wiring/DI container
│   ├── config/settings.py           Typed settings (env/.env)
│   ├── logging_setup.py             Console + JSON audit log
│   ├── models.py                    Pydantic domain models
│   ├── broker/
│   │   ├── base.py                  BrokerClient interface
│   │   └── zerodha_client.py        Kite Connect wrapper
│   ├── marketdata/
│   │   ├── websocket_manager.py     KiteTicker + reconnect
│   │   ├── candle_builder.py        Tick → candle (1m/3m/5m/15m/1h)
│   │   └── instruments.py           Instrument master cache
│   ├── strategy/
│   │   ├── indicator_engine.py      EMA/RSI/MACD/ATR/VWAP/BB/Supertrend
│   │   ├── signal_engine.py         Regime + explainable scoring
│   │   ├── options_engine.py        Chain, PCR, max-pain, IV, greeks
│   │   └── examples/                5 example strategies
│   ├── risk/risk_manager.py         Pre-trade gate, sizing, kill switch
│   ├── execution/
│   │   ├── paper_broker.py          In-memory fills + slippage + brokerage
│   │   └── order_manager.py         Orchestrator (analysis/paper/live)
│   ├── portfolio/position_manager.py
│   ├── storage/{database.py,schema.sql}
│   ├── backtest/{engine.py,metrics.py}
│   ├── alerts/notifier.py
│   └── api/routes.py                FastAPI dashboard API
├── ui/dashboard/                    React + Vite + TypeScript UI
├── config/{config.yaml,strategies.yaml}
├── scripts/{run_sample_backtest.py,zerodha_login.py}
├── tests/                           pytest scaffolding + unit tests
├── pyproject.toml
├── Makefile
└── .env.example
```

---

## Setup

### 1. Python backend

```bash
make install                 # creates .venv and installs editable + dev deps
cp .env.example .env         # fill in your values (see below)
```

### 2. Generate Zerodha access token (daily)

```bash
source .venv/bin/activate
python scripts/zerodha_login.py
# 1) Open the printed login URL, complete 2FA
# 2) Paste the `request_token` from the redirect URL
# 3) Copy the printed access_token into KITE_ACCESS_TOKEN in .env
```

### 3. Run backend

```bash
make run
# http://localhost:8000/            health JSON
# http://localhost:8000/api/health  runtime status
# http://localhost:8000/api/signals recent AI signals
# ws://localhost:8000/ws            live dashboard stream
```

### 4. Run dashboard

```bash
make ui-install
make ui-dev                  # http://localhost:5173  (proxies /api and /ws)
```

### 5. Sample backtest

```bash
make backtest
# → data/sample_backtest_report.json
```

---

## Modes & Safety

| Mode | What happens | How to unlock |
| :-- | :-- | :-- |
| `analysis` (default) | Signals logged, risk-checked, never placed. | — |
| `paper` | Signals + manual orders filled by in-memory PaperBroker with slippage & brokerage. | `APP_MODE=paper` |
| `live` | Orders placed on Zerodha. | `APP_MODE=live` **AND** `LIVE_TRADING_UNLOCK=I_UNDERSTAND_THE_RISKS` |

Additional guards at all times:

- Hard stop-loss mandatory (signal schema)
- Max daily drawdown auto-lock
- Max open positions / trades-per-day cap
- Cooldown after N consecutive losses
- Duplicate-signal suppression
- Allowed trading-hours window
- Auto square-off after `SQUARE_OFF_TIME`
- **Kill switch** (button in the dashboard or `POST /api/risk/kill`)

---

## Signal Output (example)

Every signal emitted by `SignalEngine` is explainable:

```
[nifty_momentum_breakout] BULLISH MOMENTUM_BREAKOUT on NIFTY @ 22045.50
  SL 21980.00, T1 22120.00, RR 1.90, confidence 0.72, regime TRENDING_UP
  Why:
    Close 22045.50 > prior 20-bar high 22035.00
    Volume 1.4x avg
    EMA stack bullish (9 > 21)
  Invalidation:
    Close back below 22035.00 within 2 bars
    MACD histogram flips negative
  Suggested qty: 25   Risk: ₹1,625   Expected RR: 1.9
```

---

## Scoring Layer

| Step | Contribution |
| :-- | --: |
| Strategy base confidence | up to +1.00 |
| Regime aligns with direction | +0.15 |
| Indicator stack agrees (EMA/MACD/RSI/VWAP) | up to +0.10 |
| Bias-aligned candle pattern | up to +0.05 |
| RR < 1.3 | −0.20 |
| VOLATILE regime × mean-reversion | −0.10 |

Result is clipped to `[0, 1]`. This scorer is deliberately explainable; drop
in an ML model by replacing `SignalEngine._score()`.

---

## Strategies Included

- **Nifty momentum breakout** — 20-bar high break with volume & EMA stack.
- **Bank Nifty reversal scalp** — RSI extreme + candle reversal at S/R.
- **Equity intraday breakout** — Opening range break with VWAP filter.
- **Options premium momentum** — Accelerating premium + bullish indicators.
- **Futures trend-follow** — Supertrend + EMA50 bias + pullback.

Add your own by subclassing `BaseStrategy` and registering it with
`SignalEngine`.

---

## Dashboard

- **Overview** — mode, P&L, risk budget, connection health.
- **Watchlist** — Nifty / Bank Nifty / equities with signal badges.
- **AI Signals** — recent signals with explanation, plus a simulator.
- **Option Chain Insights** — PCR, max-pain, walls, IV.
- **Positions / Trade Blotter / Orders**.
- **Risk Monitor** — budget usage bar, guards, counters.
- **Alerts / Logs**.
- **Backtest** — how to run and where the report lands.

All panels subscribe to `GET /api/*` and update on a 2.5 s poll. A WebSocket
stream at `/ws` is also exposed for push updates.

---

## Tests

```bash
make test      # unit tests for indicators, candles, paper broker, risk manager
```

---

## Non-negotiables (built into the code)

- No promise of profits.
- No fake "100% accurate AI".
- Signals always include reasons and invalidation.
- Defaults to analysis-only mode.
- Live trading requires an explicit unlock phrase.
- Every signal and order is written to the SQLite audit log (`audit_log`, `signals`, `orders`, `trades`).

---

## License

MIT — see header in each file. Don't trade with money you can't afford to lose.
