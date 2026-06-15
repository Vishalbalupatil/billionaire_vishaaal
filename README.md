# AI Trader — Nifty 50 Options + Equity Scanner

> **AI-powered autonomous trading platform for Indian equity & options markets
> integrated with Zerodha Kite Connect.**

**This is a decision-support and execution tool. It is NOT financial advice.
No profits are guaranteed. Always paper-trade new strategies before going live.
Live orders are locked behind an explicit unlock phrase.**

---

## Features

- **AI Ensemble Model** — XGBoost classifier + rule-based fallback for
  directional prediction with confidence scoring
- **Autonomous Trading** — Full auto-trading loop: scan → identify → enter →
  manage → exit. The system trades by itself when connected to market data.
- **Equity Scanner** — Scans Nifty 50 stocks for momentum, breakout, and
  volume surge setups with ranked scoring
- **Chart Pattern Recognition** — Detects head & shoulders, double tops/bottoms,
  ascending/descending triangles, bull/bear flags
- **Multi-Timeframe Trend Analysis** — EMA alignment, SuperTrend, ADX, RSI
  across 5m/15m/1h/daily with weighted consensus
- **Auto Strategy Selection** — Picks optimal options strategy (spreads,
  straddles, iron condors) based on market regime + IV level
- **Full Options Analytics** — Black-Scholes pricing, Greeks (delta/gamma/
  theta/vega), implied volatility, max pain, PCR, call/put walls
- **Risk Management** — 2% per-trade risk, portfolio Greeks limits, daily loss
  kill switch, auto square-off before market close
- **3 Execution Modes** — Analysis (signals only), Paper (simulated fills),
  Live (real orders via Kite Connect)
- **Real-time Dashboard** — React + TypeScript + Tailwind CSS with dark theme,
  live signal feed, equity scanner, auto-trader monitor, payoff diagrams, risk monitor
- **Market Data Pipeline** — Kite WebSocket ticks → multi-timeframe candle
  builder → indicator engine → AI signals → auto-execution

## Architecture

```
src/ai_trader/
├── app.py                 FastAPI server
├── cli.py                 CLI (serve, train, status)
├── config.py              Typed settings (env vars)
├── models/                Pydantic domain models (+ scanner models)
├── ai/                    ML model, features, signals, regime detection
├── scanner/               Equity scanner, chart patterns, trend analysis
├── options/               Greeks, chain analysis, strategy selector
├── broker/                Zerodha + Paper broker
├── market_data/           WebSocket feed, candle builder, instruments
├── risk/                  Risk management, position sizing
├── strategy/              Strategy engine, auto-trader, technical indicators
├── execution/             Order management, trading schedule
├── storage/               SQLite persistence
└── api/                   REST + WebSocket endpoints

ui/dashboard/              React dashboard (Vite + TypeScript + Tailwind)
├── views/Overview         Dashboard overview
├── views/Signals          AI signal feed
├── views/Scanner          Equity scanner + chart patterns + trends
├── views/AutoTrader       Auto-trading monitor + activity log
├── views/Strategies       Options strategy payoff diagrams
├── views/Positions        Open positions
├── views/RiskMonitor      Risk status + kill switch
└── views/Settings         Configuration
```

## How Auto-Trading Works

1. **Scan** — Every cycle, the equity scanner analyzes all Nifty 50 stocks
   for momentum, breakout, and volume surge setups
2. **Identify** — Chart pattern recognition detects classical patterns
   (H&S, double top/bottom, triangles, flags) for confirmation
3. **Trend Filter** — Multi-timeframe trend analysis ensures trades align
   with the dominant trend direction
4. **Enter** — If score ≥ 70 (or ≥ 60 with pattern confirmation), risk checks
   pass, and trend aligns → auto-places the order
5. **Monitor** — Tracks all active trades, updating P&L in real-time
6. **Exit** — Automatically exits on stop-loss hit, target hit, or market
   close (auto square-off at 15:15 IST)

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ (for dashboard)
- Zerodha Kite Connect API key

### Setup

```bash
# Clone and install
git clone https://github.com/Vishalbalupatil/billionaire_vishaaal.git
cd billionaire_vishaaal

# Create .env from template
cp .env.example .env
# Edit .env with your Kite API key/secret

# Install Python deps
make install

# Install UI deps
make dev

# Train the AI model (optional — uses synthetic data for demo)
make train
```

### Run

```bash
# Start API server (paper mode by default)
make serve

# In another terminal, start the dashboard
make ui

# Open http://localhost:5173
```

### Daily Authentication (Zerodha)

1. Visit the login URL shown in the Settings page
2. Complete 2FA on Zerodha
3. Copy the `request_token` from the redirect URL
4. Paste it in the Settings page → Create Session

## Trading Modes

| Mode | Orders | Data | Use Case |
|------|--------|------|----------|
| `analysis` | None | Live/historical | Signal generation only |
| `paper` | Simulated | Live/historical | Testing strategies |
| `live` | Real (Kite) | Live | Actual trading |

## Options Strategies

The AI auto-selects from:

| Regime | IV | Strategy |
|--------|-----|----------|
| Trending Up | Low-Med | Bull Call Spread |
| Trending Down | Low-Med | Bear Put Spread |
| Range-bound | High | Iron Condor / Short Strangle |
| Volatile | High | Short Straddle |
| Quiet | Low | Long Straddle |

## Risk Management

- **Per-trade risk**: Configurable % of capital (default 2%)
- **Daily loss limit**: Auto kill switch when breached (default 5%)
- **Portfolio Greeks**: Delta and gamma limits
- **Auto square-off**: Before market close (default 15:15 IST)
- **Kill switch**: Manual or automatic halt of all trading
- **Trend alignment**: Won't enter bullish trades in bearish trends (and vice versa)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | System status |
| `/api/signals` | GET | Recent AI signals |
| `/api/strategies` | GET | Selected options strategies |
| `/api/positions` | GET | Open positions |
| `/api/risk` | GET | Risk status |
| `/api/risk/kill-switch` | POST | Toggle kill switch |
| `/api/scanner/results` | GET | Equity scan results (ranked) |
| `/api/scanner/patterns` | GET | Detected chart patterns |
| `/api/scanner/trends` | GET | Trend analysis per symbol |
| `/api/auto-trader/status` | GET | Auto-trader status |
| `/api/auto-trader/trades` | GET | Active auto-trades |
| `/api/auto-trader/log` | GET | Auto-trader activity log |
| `/api/auth/login-url` | GET | Kite login URL |
| `/api/auth/session` | POST | Create Kite session |
| `/ws/live` | WS | Real-time updates |

## License

MIT
