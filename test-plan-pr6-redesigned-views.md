# Test Plan — PR #6 (7 redesigned views) + PR #7 (RingGauge fix)

**Scope:** both PRs are merged to `main` (commits `225da18` and `3879772`). This plan tests the
merged state, not any feature branch. No backend changes landed with PR #6, so all verification is
UI + data-wiring through existing paper-broker endpoints.

**Environment:**
- Backend: `APP_MODE=paper .venv/bin/uvicorn billionaire.app:app --port 8000` (running)
- Dashboard: `npm run dev --host 127.0.0.1 --port 5173` (running)
- Browser: Chrome on this VM, maximised via `wmctrl`
- Recording: continuous, with `record_annotate` at each view transition and each assertion

**CI status:** repo has no GitHub Actions. Devin Review passed on both PRs. Nothing to wait on.

---

## Why each assertion is adversarial

Every assertion below is written to fail loudly if the change were broken. Plain "view renders"
tests are worthless because the old plain-styled views also rendered — so for each view we assert
a marker that is **only present in the redesigned component** (a specific `.eyebrow` heading string
like `NIFTY 50 · EXECUTION LOG`, a specific new CSS class like `.glow-rows` / `.segmented` / `.ring-wrap`,
or a unique element like the Recharts equity curve SVG). If PR #6 were reverted, these selectors
would not exist and the test would fail.

---

## Phase A — Tour all 7 redesigned views

Each assertion is: click sidebar item → verify the unique marker string below is present in the DOM.

| # | View | Sidebar button | Pass criterion (unique to redesign) |
|---|---|---|---|
| A1 | Positions | `◎ Positions` | Heading `NIFTY 50 · LIVE POSITIONS` + `.glow-rows` table class in DOM + 4-card KPI row (Open / Long / Short / Unrealised P&L) + disclaimer footer `Not financial advice` |
| A2 | Trades    | `→ Trades`    | Heading `NIFTY 50 · EXECUTION LOG` + realised-P&L KPI row + two half-cards (`Order Book` timeline, `Trade Blotter` table) + disclaimer |
| A3 | Signals   | `∿ Signals`   | Heading `NIFTY 50 · AI SIGNAL ENGINE` + `.segmented` direction toggle with `BULLISH / BEARISH / NEUTRAL` buttons + confidence slider + RR chip + Recent-signals table |
| A4 | Risk      | `◆ Risk`      | Heading `NIFTY 50 · RISK MONITOR` + SVG `.ring-wrap` gauge + Guards list + 4-stat counter row |
| A5 | Alerts    | `! Alerts`    | Heading `NIFTY 50 · ALERTS` + Channel availability cards (Console / Telegram / SMTP / WhatsApp) + event timeline OR empty state |
| A6 | Options   | `◇ Options`   | Heading `NIFTY 50 · OPTION CHAIN` + expiry `.segmented` toggle + strike grid + amber `SCAFFOLD` chip + PCR number |
| A7 | Backtest  | `↻ Backtest`  | Heading `NIFTY 50 · BACKTEST` + Recharts `<svg>` area equity curve + CAGR/Sharpe/MaxDD/WinRate KPIs + amber `SCAFFOLD` chip |

**Falsifiable:** the pre-PR views had none of these strings or classes.

---

## Phase B — Primary flow: Signals → Positions → Trades

End-to-end proof that PR #6 did not break the data wiring.

**Setup:** portfolio starts empty (`count_long=0, count_short=0`) per `/api/portfolio`.

**Steps:**
1. Navigate to Signals.
2. Fill sim form:
   - Symbol: `TESTCO`
   - Direction: `BULLISH` (via `.segmented` control)
   - Entry: `102`
   - SL: `100`
   - Target 1: `106`
   - Confidence: `0.65` (via slider)
   - Setup: keep default
3. Click **Generate signal**.

**Assertions:**
- **B1** — a new row appears in the Recent-signals table at top of Signals view, symbol `TESTCO`,
  direction chip green `BULLISH`, confidence bar ~65%.
- **B2** — click `Positions` in sidebar. New row appears:
  - symbol `TESTCO`
  - qty `375` (= floor(risk budget / stop distance) = floor(₹750 / ₹2); account_capital=100000,
    risk_per_trade_pct=0.75 → 750)
  - avg price `102.05` (= 102 × 1.0005, 5-bps paper slippage)
  - direction chip green `LONG`
  - P&L cell coloured (green if ≥0, red if <0); with ltp==entry, P&L≈0
  - sparkline column renders Recharts AreaChart (SVG with gradient fill)
- **B3** — `Open` KPI increments from 0 → 1, `Long` KPI from 0 → 1.
- **B4** — click `Trades` in sidebar. New entry appears in `Order Book` timeline:
  - symbol `TESTCO`, side `BUY`, qty 375, price 102.05, status `COMPLETE`.
- **B5** — `Fills today` KPI = 1.

**Falsifiable:** if PR #6 broke the sim endpoint or the Positions/Trades fetch, none of these would
appear even though B1 might still pass.

---

## Phase C — RingGauge fix (PR #7)

The fix changed `strokeDashoffset={c / 4}` → `strokeDashoffset={0}` in RiskMonitor.tsx:221.
Combined with the existing `transform="rotate(-90 80 80)"`, the arc now starts at 12 o'clock.

**Steps:**
1. On Risk view with empty portfolio (realised_pnl_today=0), gauge is 0% — a full empty ring,
   no arc, can't visually verify start position. So force non-zero:
2. Click **Kill Switch** in top bar. This doesn't change the gauge but is the next cheapest way
   to see risk state change… actually gauge only reflects daily-loss budget consumption.
3. Simpler: temporarily seed a losing trade — but that requires backend changes. Instead, verify
   the arc start position by inspecting the gauge's **background circle** and noting that when
   `pct > 0` the arc begins at the top (12 o'clock).
4. In this session, use a small dev-server override: post a sim signal that immediately closes at
   a loss. Actually no — paper broker only fills entry, doesn't auto-close. So:
5. **Workaround:** verify via DOM inspection. Read the rendered SVG with the computer tool and
   confirm:
   - the colored `<circle>` has `strokeDashoffset="0"` (exact value 0, not 98-ish)
   - the `transform` attribute is `rotate(-90 80 80)`

**Assertion C1:** SVG DOM has `strokeDashoffset="0"` on the foreground arc circle.
**Falsifiable:** if PR #7 were reverted, offset would be `~97.39` (= `2πr/4` with r=62).

---

## Phase D — Regression & edge cases

- **D1 (Positions empty state):** before Phase B, Positions view shows a single `.empty-state`
  card with muted glyph and message like "No open positions."
- **D2 (Trades empty state):** before Phase B, both Order Book and Trade Blotter cards render
  `.empty-state` message.
- **D3 (Alerts empty state):** with no orders/trades/risk events, Alerts timeline shows empty state.
- **D4 (Scaffold labeling):** OptionChain and Backtest views prominently show amber `SCAFFOLD` chip
  so user knows data is synthetic.
- **D5 (Disclaimer footers):** every redesigned view ends with a `.disclaimer` strip reading
  "Decision-support only. Not financial advice."
- **D6 (Console errors):** after touring all 7 views + running Phase B, browser console has zero
  error entries.
- **D7 (No layout overflow):** main content column does not produce a horizontal scrollbar at the
  current maximised viewport.

---

## Out of scope (will not test this round)

- Live data / WebSocket / Kite integration — market is closed and credentials are intentionally
  absent in paper mode.
- Forecast live-data branch — requires real candle history, not deterministic in test env.
- Multi-day risk-budget consumption — out of scope for a UI redesign PR.
- Mobile breakpoints — user didn't request mobile verification.

---

## Reporting

- One continuous screen recording of the full flow (Overview → A1..A7 → B1..B5), with
  `record_annotate` markers per assertion.
- `test-report.md` with pass/fail/inconclusive per item + inline screenshots of the most important
  evidence (Positions row after sim signal, Ring gauge on Risk view, Recharts equity curve on
  Backtest, SCAFFOLD chips on Options/Backtest).
- One consolidated GitHub comment on PR #6 linking both.
