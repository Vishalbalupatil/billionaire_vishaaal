# Testing the billionaire_vishaaal dashboard

Smoke-tests any UI change against the real backend without needing Zerodha
credentials or market hours. Use this for any PR that touches the dashboard
(`ui/dashboard/`) or the FastAPI routes under `src/billionaire/api/`.

## Devin Secrets Needed

None for paper-mode testing. For live-mode testing you need `KITE_API_KEY`,
`KITE_API_SECRET` (both already saved as persistent user secrets), plus a
fresh `KITE_ACCESS_TOKEN` which expires daily — mint it on the day via
`python scripts/zerodha_login.py`, do NOT save it as a secret.

## One-time setup per sandbox

```bash
cd ~/repos/billionaire_vishaaal         # or wherever it's cloned
python3.11 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e ".[dev]"
(cd ui/dashboard && npm install)
```

## Boot sequence (paper mode — no creds needed)

Two separate shells, both left running:

```bash
# shell 1 — backend
APP_MODE=paper .venv/bin/uvicorn billionaire.app:app --port 8000

# shell 2 — dashboard
(cd ui/dashboard && npm run dev -- --host 127.0.0.1 --port 5173)
```

Sanity check before opening the browser:

```bash
curl -s http://127.0.0.1:8000/api/health | jq
# expect: {"mode":"paper","broker":"paper-only",...}
```

Open `http://127.0.0.1:5173/` in Chrome. Maximise with
`wmctrl -r :ACTIVE: -b add,maximized_vert,maximized_horz` before recording.

## Deterministic paper-broker math (assert exact values, not "something")

With defaults (`ACCOUNT_CAPITAL=100000`, `RISK_PER_TRADE_PCT=0.75`, slippage 5 bps):

| Input signal | Resulting position |
|---|---|
| `entry=102, sl=100` (₹2 SL distance, risk budget = 100000 × 0.0075 = ₹750) | qty = `floor(750/2) = 375`, avg = `102 × 1.0005 = 102.05`, net = `375 × 102.05 = ₹38,268.75` |

So after submitting that exact sim signal, the UI MUST show
`TESTCO LONG 375 @ 102.05 / net ₹38,268.75`. If any of those three numbers is
off, it's a real regression — the paper broker did not behave as specified.

## Primary flow used to smoke-test any redesign

1. Signals tab → set symbol=`TESTCO`, direction=`BULLISH`, entry=102, SL=100,
   target=106, conf=0.65 → Generate signal.
2. Expect a new row at top of Recent Signals.
3. Positions tab → expect `TESTCO LONG 375 @ 102.05`, Open=1, Long=1.
4. Trades tab → expect `BUY TESTCO ×375 MARKET COMPLETE · paper · avg 102.05`
   in Order Book. Blotter stays empty (paper broker does NOT auto-close —
   "fills" is the exit count).
5. Risk tab → inspect the ring gauge (see DOM probe below).

After restart, signals persist (SQLite) but positions reset (in-memory).

## CSS markers that prove the AI-website redesign is rendering

Each redesigned view has a unique `.eyebrow` heading. If it's missing, the
view is either the pre-redesign component or a broken fallback.

| View | Expected `.eyebrow` text |
|---|---|
| Overview  | `NIFTY 50 · AI OVERVIEW` |
| Forecast  | `NIFTY 50 · AI FORECAST` |
| Watchlist | `NIFTY 50 · WATCHLIST` |
| Positions | `NIFTY 50 · LIVE POSITIONS` |
| Trades    | `NIFTY 50 · EXECUTION LOG` |
| Signals   | `NIFTY 50 · AI SIGNAL ENGINE` |
| Risk      | `NIFTY 50 · RISK MONITOR` |
| Alerts    | `NIFTY 50 · ALERTS` |
| Options   | `NIFTY 50 · OPTION CHAIN` |
| Backtest  | `NIFTY 50 · BACKTEST` |

Options and Backtest must ALSO show an amber `SCAFFOLD` chip — data is
synthetic until real feeds are wired. Every view ends with a `.disclaimer`
strip reinforcing "not financial advice".

## Ring gauge invariant (PR #7 fix)

On Risk tab, the foreground `<circle>` inside `.ring-wrap svg` MUST have
`stroke-dashoffset="0"` and `transform="rotate(-90 80 80)"`. Probe from
DevTools console:

```js
JSON.stringify(Array.from(document.querySelectorAll('.ring-wrap svg circle'))
  .map(c => ({stroke: c.getAttribute('stroke'),
              offset: c.getAttribute('stroke-dashoffset'),
              transform: c.getAttribute('transform')})));
```

Expected second element: `stroke-dashoffset: "0"`. If it reads ~97.39
(`2πr/4` with r=62) the arc starts at 9 o'clock instead of 12 — regression.

## Things to watch for that aren't bugs

- Recharts emits `The width(-1) and height(-1) of chart should be greater
  than 0` warnings when sparklines mount off-screen. Cosmetic — charts
  render correctly when scrolled into view. Might be fixable with
  `<ResponsiveContainer>` aspect ratio but is not blocking.
- `signal only works in main thread` Twisted traceback from kiteconnect on
  macOS is cosmetic; ticker still connects. Only relevant in live mode.
- Portfolio resets between uvicorn restarts (in-memory) but signals and
  orders persist in SQLite at `data/billionaire.db`. This asymmetry can
  look like a bug but is by design.

## Live-mode testing (only when necessary)

Requires: paid Kite Connect subscription, fresh daily `KITE_ACCESS_TOKEN`,
Indian market hours (09:15–15:30 IST Mon–Fri), `LIVE_TRADING_UNLOCK=I_UNDERSTAND_THE_RISKS`.
Start with the smallest possible size (`RISK_PER_TRADE_PCT=0.1`) and verify
`/api/health` shows `broker: "zerodha"` (not `paper-only`) before trusting
anything.

## Reporting

Record the full walkthrough with `computer(action="record_start")` and use
`record_annotate` with `type="test_start"` / `type="assertion"` for each
view. One-continuous-flow recordings are more convincing than many short
clips. Attach the resulting mp4 + a `test-report.md` with inline screenshots
of the before/after evidence.
