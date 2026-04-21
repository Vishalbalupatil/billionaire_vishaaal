# Test Plan — PR #1: Paper-mode demo fills

PR: https://github.com/Vishalbalupatil/billionaire_vishaaal/pull/1

## What changed (user-visible)

Before the fix, clicking **Generate** on the Signals tab (paper mode) logged the signal but left the order stuck in `OPEN`, and the Positions tab stayed empty. After the fix:

1. `PaperBroker._process_pending` now fills MARKET orders as soon as any LTP arrives for that instrument token. (`src/billionaire/execution/paper_broker.py:62-65`)
2. `POST /api/sim/signal` now accepts `instrument_token` and, when `seed_ltp=True` (default), primes the paper broker's LTP cache at the signal's entry price before handing off to the order manager. (`src/billionaire/api/routes.py:48-60, 152-181`)

Net effect: a paper-mode signal becomes a filled order and an open position in one click — no separate tick call required.

## Test environment

- Backend: `APP_MODE=paper uvicorn billionaire.app:app --port 8000` with `ACCOUNT_CAPITAL=100000`, `RISK_PER_TRADE_PCT=0.75`.
- Dashboard: `cd ui/dashboard && npm run dev` (Vite proxies `/api` to `localhost:8000`, see `ui/dashboard/vite.config.ts`).
- Fresh SQLite DB — rm `data/billionaire.db` between restarts so duplicate-guard and trade counters start clean.

## Primary flow (recorded in browser)

Values chosen so every assertion has a concrete expected number:
`entry=102.00`, `stop_loss=100.00`, `target1=106.00`, `confidence=0.65`, symbol=`TESTCO` (equity → segment=EQUITY).

Risk math for assertion 4:
- budget = 100 000 × 0.75 % = **₹750**
- risk/unit = 102 − 100 = **₹2**
- expected qty = floor(750 / 2) = **375**

Expected paper fill price with 5 bps BUY slippage: `102 × (1 + 0.0005) = 102.051` → displayed as **102.05**.

### Steps & assertions

| # | Action | Expected (pass) | If broken (fail signature) |
|---|---|---|---|
| 1 | Open dashboard at `http://localhost:5173`. | Top bar shows `MODE · PAPER` badge (neon), broker pill reads `paper-only`. | Badge reads `ANALYSIS` or `LIVE`; broker reads `zerodha`. |
| 2 | Click **Positions** tab. | Table empty, `Open=0`, `Long=0`, `Short=0`. | Any non-zero count on a clean DB. |
| 3 | Click **Signals** tab. Fill form: strategy=`equity_intraday_breakout`, symbol=`TESTCO`, direction=`BULLISH`, entry=`102`, sl=`100`, t1=`106`, conf=`0.65`. Click **Generate**. | Within one 3-second refresh, `Recent Signals` table shows a new row with those exact numbers, regime shown. | Row never appears, or appears with empty regime/reasons. |
| 4 | Still on Signals tab: open browser devtools → Network → inspect the `POST /api/sim/signal` response. | JSON `placed=true`, `order.status="COMPLETE"`, `order.avg_price` within `[102.04, 102.06]`, `order.order_type="MARKET"`, `order.side="BUY"`. | `placed=false`, or `status="OPEN"`, or `avg_price=0`. `status="OPEN"` is the exact pre-fix bug. |
| 5 | Click **Positions** tab. | One row: `TESTCO`, qty=`375`, avg=`102.05`, ltp=`102.05`, product=`MIS`. KPI: `Open=1`, `Long=1`, `Short=0`, `Net Exposure ≈ ₹38,269`. | Row missing (pre-fix bug), or qty ≠ 375 (risk model misapplied). |
| 6 | Top bar: click **Kill Switch** (red button). Click **Signals** tab, press **Generate** again with the *same* form values. | Top bar button label flips to `Release Kill Switch`. `POST /api/sim/signal` response: `placed=false`, reason contains `"Kill switch is engaged"`. No new position. | Order places anyway; kill switch ignored. |
| 7 | Click **Release Kill Switch**, then **Generate** once more with the *same* form values. | `placed=false`, reason contains `"duplicate"`. Positions tab still shows qty=`375` (no second fill). | A second row appears or qty doubles. |

### Regression checks (shell only — not recorded)

| # | Command | Expected |
|---|---|---|
| R1 | `APP_MODE=analysis uvicorn …` + `curl -XPOST /api/sim/signal …` (same body as step 3). | HTTP 200, `{"placed": false, "reason": "app mode is analysis"}` (or equivalent). No entry in `/api/portfolio`. |
| R2 | `APP_MODE=live` only (no `LIVE_TRADING_UNLOCK`) + startup. | Startup logs refuse live mode with message containing both `APP_MODE=live` **and** `LIVE_TRADING_UNLOCK`. App should fall back or exit — exact behaviour captured in report. |
| R3 | `APP_MODE=live` **and** `LIVE_TRADING_UNLOCK=I_UNDERSTAND_THE_RISKS` with no Kite creds. | Startup logs: falls back to paper mode (proves two-flag unlock logic is the decision point). `/api/health` returns `mode=paper` or `broker=paper-only`. |

### Why these tests would fail if the change was broken

- Step 4 specifically checks `order.status="COMPLETE"` and a precise `avg_price`. Pre-fix, `status="OPEN"` and `avg_price=0` — visibly different.
- Step 5 checks the exact computed quantity 375. A default quantity or `0` would fail the assertion.
- Step 6 requires the kill-switch reason string to match; a missing pre-trade check would let the order through.
- Step 7 requires the duplicate-guard reason string; without it a second fill would appear.

## Out of scope

- Live Zerodha order placement (no creds, no market hours).
- WebSocket reconnection, options chain analytics, backtest runner — untouched by this PR.
- Strategy scoring math — covered by unit tests, not runtime.
