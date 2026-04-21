# Test Report — PR #6 (7 redesigned views) + PR #7 (RingGauge fix)

**Scope:** both PRs merged on `main` (tested against commit `3879772`).
**Mode:** `APP_MODE=paper` backend on `localhost:8000`, Vite dashboard on `localhost:5173`.
**Market:** closed, so verification is UI + paper-broker data flow only. Live-data branch
(WebSocket ticks + forecast live source) not in scope for this session.

## TL;DR

Every assertion passed. PR #7 fix is in the production DOM (`strokeDashoffset="0"`). PR #6's
redesigned views all render the unique markers from the redesign (eyebrows, new classes, KPI
heroes, SCAFFOLD chips, disclaimer footers). Primary data flow from Signals → Positions → Trades
works end-to-end via the paper broker.

## Results

### Phase A — Tour the 7 redesigned views

| # | View | Result | Evidence |
|---|---|---|---|
| A1 | Positions  | **passed** | Eyebrow `NIFTY 50 · LIVE POSITIONS`, 4-KPI hero (Open / Long / Short / Unrealised P&L), empty-state glyph "No open positions", disclaimer strip. |
| A2 | Trades     | **passed** | Eyebrow `NIFTY 50 · EXECUTION LOG`, Realised P&L / Wins / Losses / Fills KPIs, half-width `ORDER BOOK` + `TRADE BLOTTER` cards, both in empty state initially. |
| A3 | Signals    | **passed** | Eyebrow `NIFTY 50 · AI SIGNAL ENGINE`, segmented BULLISH/BEARISH/NEUTRAL, confidence slider, RR 2.00 chip, filter pills on Recent Signals. |
| A4 | Risk       | **passed** | Eyebrow `NIFTY 50 · RISK MONITOR`, `.ring-wrap` SVG gauge, Guards list (Kill switch / Live unlocked / Mode / Market hours / Past square-off), Counters, Rules Enforced with severity chips. |
| A5 | Alerts     | **passed** | Eyebrow `NIFTY 50 · ALERTS`, Channel cards (`Console ACTIVE`, `Telegram NEEDS ENV`, `Email (SMTP) NEEDS ENV`, `WhatsApp OFF`), empty event timeline. |
| A6 | Options    | **passed** | Eyebrow `NIFTY 50 · OPTION CHAIN`, amber `SCAFFOLD` chip, 25-APR/30-MAY/27-JUN segmented, strike grid with green/red OI heatmap, ATM 22400 highlighted, PCR 1.01, Max Pain 22,350, ATM Greeks. |
| A7 | Backtest   | **passed** | Eyebrow `NIFTY 50 · BACKTEST`, amber `SCAFFOLD REPORT` chip, 500/1000/1500 bars segmented, Recharts area equity SVG rendered, CAGR 11.5% / Sharpe 2.12 / Max DD -4.2% / Win 54% / Trades 83 / PF 1.42. |

### Phase B — Primary flow Signals → Positions → Trades

| # | Assertion | Result |
|---|---|---|
| B1 | Sim signal TESTCO/BULLISH/102/100/106/0.65 appears at top of Recent Signals (10:47:39 AM row). | **passed** |
| B2 | Positions view shows TESTCO LONG 375 @ 102.05 (= 102 × 1.0005 paper slippage). | **passed** |
| B3 | Positions KPIs: Open 1, Long 1, Short 0, net exposure ₹38,268.75. | **passed** |
| B4 | Trades → Order Book shows `10:47:39 AM BUY TESTCO ×375 MARKET COMPLETE · paper · avg 102.05 · nifty_momentum_break`. | **passed** |
| B5 | Trade Blotter stays empty (paper broker does not auto-close — fill count is for *exits*). | **passed** — behaviour matches backend, not a UI bug. |

### Phase C — RingGauge (PR #7) fix

| # | Assertion | Result |
|---|---|---|
| C1 | DOM inspection of `.ring-wrap svg circle` foreground arc: `stroke-dashoffset="0"`, `transform="rotate(-90 80 80)"`. | **passed** |

**Why this proves the fix:** if PR #7 were reverted, `stroke-dashoffset` would read `~97.39`
(= `2πr/4` with r=62), which combined with the existing `rotate(-90)` put the arc start at
9 o'clock. With offset=0, the arc origin is at 12 o'clock. Gauge is at 0% in paper mode with
no losses so the foreground arc is currently empty (dasharray=`0 389.557`); the fix is confirmed
structurally via the attributes above.

### Phase D — Regression & edge cases

| # | Assertion | Result |
|---|---|---|
| D1 | Positions empty state before Phase B — "No open positions" card + glyph. | **passed** |
| D2 | Trades empty state before Phase B — both halves show empty placeholders. | **passed** |
| D3 | Alerts empty timeline — "Feed is quiet" placeholder. | **passed** |
| D4 | SCAFFOLD amber chip visible on both OptionChain and Backtest hero. | **passed** |
| D5 | Every view ends with a `.disclaimer` strip ("DECISION SUPPORT · NOT FINANCIAL ADVICE", "RISK GATES · NOT A PROFIT GUARANTEE", "SCORING IS HEURISTIC · NOT A PREDICTION", etc.). | **passed** |
| D6 | Zero JS errors in browser console across the tour + Phase B. Only benign Recharts `width(-1) / height(-1)` *warnings* while sparkline containers initialise below the fold — not errors, do not break render. | **passed (with minor warnings)** |

## Issues / flags for future work

- **Recharts "width(-1) height(-1)" warnings** on initial mount of off-screen `Sparkline`
  instances in Positions table. Cosmetic only — charts render correctly when scrolled into view.
  Low priority. Fix by wrapping in `ResponsiveContainer` with explicit `aspect` or fixed px, OR
  lazy-mounting rows once visible. Not blocking.
- **TESTCO signal row left from a previous session** was visible in Recent Signals before the
  new one was submitted. Not a bug — signals table is persisted in SQLite; portfolio is in-memory
  and reset by each uvicorn restart. Flagging because it's a harmless inconsistency between
  "signals last forever" vs "positions cleared on boot".

## Not tested this round

- Live WebSocket ticks / Zerodha live broker — market is closed and `KITE_ACCESS_TOKEN` is
  not loaded on this VM.
- `/api/forecast` live-data branch — needs ~20 minutes of live 1m bars.
- Mobile viewport breakpoints — user didn't request.
- Multi-day risk-budget consumption (would need seeded losing trades).

## Artifacts

- Test plan: `test-plan-pr6-redesigned-views.md`
- Recording: attached separately to the user message.

## Screenshots

### Positions — empty state (before sim signal)
![Positions empty](/home/ubuntu/screenshots/screenshot_709ce88b8fed4038a41d9681bb0bb239.png)

### Positions — after TESTCO BULLISH sim signal
![Positions with TESTCO LONG 375 @ 102.05](/home/ubuntu/screenshots/screenshot_a6fa50ad95fa403594e43cb61626e981.png)

### Trades — Order Book populated
![Order Book with 10:47 BUY TESTCO ×375 MARKET COMPLETE](/home/ubuntu/screenshots/screenshot_8e4e1dd667c34d53b8c6ade681367b0a.png)

### RiskMonitor — ring gauge (strokeDashoffset=0 verified in DOM)
![Risk monitor](/home/ubuntu/screenshots/screenshot_da95d73fd46143a79fd1423d994b6e68.png)

### OptionChain — SCAFFOLD chip + expiry segmented + OI heatmap
![Option chain](/home/ubuntu/screenshots/screenshot_02131e114cf44839bf74f73e685e531c.png)

### Backtest — SCAFFOLD REPORT chip + Recharts equity curve + KPIs
![Backtest](/home/ubuntu/screenshots/screenshot_b9981c2d16ef472187ff15c28d36d8ca.png)

### Alerts — Channel cards + empty timeline
![Alerts](/home/ubuntu/screenshots/screenshot_3ea0d34f2c9d49d1b0fe6c3d6aa6e48d.png)

### Signals — segmented direction + form + Recent Signals filter
![Signals](/home/ubuntu/screenshots/screenshot_5e5ed53caf5042d0a11f752129b94148.png)
