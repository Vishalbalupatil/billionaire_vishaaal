import { useEffect, useState } from "react";
import { api, type ForecastResp, type HealthResp, type PortfolioResp, type RiskStatus } from "../api";
import ForecastChart from "../components/ForecastChart";

function fmt(n: number | undefined) {
  if (n === undefined || Number.isNaN(n)) return "—";
  return n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

export default function Overview({
  health,
  risk,
  portfolio,
}: {
  health: HealthResp | null;
  risk: RiskStatus | null;
  portfolio: PortfolioResp | null;
}) {
  const [forecast, setForecast] = useState<ForecastResp | null>(null);

  useEffect(() => {
    let cancel = false;
    async function tick() {
      try {
        const r = await api.forecast("NIFTY", "intraday", 30);
        if (!cancel) setForecast(r);
      } catch { /* backend down */ }
    }
    tick();
    const t = setInterval(tick, 5000);
    return () => {
      cancel = true;
      clearInterval(t);
    };
  }, []);

  const biasClass =
    forecast?.bias === "BULLISH" ? "up" : forecast?.bias === "BEARISH" ? "down" : "flat";
  const biasArrow =
    forecast?.bias === "BULLISH" ? "↑" : forecast?.bias === "BEARISH" ? "↓" : "→";

  return (
    <div>
      <div className="grid">
        {/* HERO */}
        <div className="card hero glow">
          <div className="eyebrow">NIFTY 50 · AI OVERVIEW</div>
          <h1>Nifty projected path · intraday 30m</h1>
          <div className="muted small" style={{ maxWidth: 680 }}>
            Heuristic log-return projection with 95% confidence band. This is a
            scaffold, not a real prediction.{" "}
            <strong style={{ color: "var(--neon-amber)" }}>Not financial advice.</strong>
          </div>
          <div className="row spread" style={{ marginTop: 16, alignItems: "flex-start" }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              {forecast ? (
                <ForecastChart
                  points={forecast.points}
                  lastPrice={forecast.last_price}
                  bias={forecast.bias}
                />
              ) : (
                <div className="chart-wrap" style={{ display: "grid", placeItems: "center" }}>
                  <span className="muted tiny">Loading forecast…</span>
                </div>
              )}
            </div>
            <div
              className="col"
              style={{
                flex: "0 0 200px", marginLeft: 18, paddingLeft: 18,
                borderLeft: "1px dashed rgba(130,200,255,0.15)",
              }}
            >
              <div className="muted tiny">BIAS</div>
              <div className="row" style={{ gap: 10 }}>
                <div className={`bias-arrow ${biasClass}`}>{biasArrow}</div>
                <div>
                  <div style={{ fontFamily: "Orbitron, sans-serif", fontSize: 16 }}>
                    {forecast?.bias ?? "—"}
                  </div>
                  <div className="muted tiny">
                    conf {forecast ? (forecast.confidence * 100).toFixed(0) : "—"}%
                  </div>
                </div>
              </div>
              <div style={{ marginTop: 14 }}>
                <div className="muted tiny">LAST</div>
                <div className="mono" style={{ fontSize: 18 }}>
                  {forecast?.last_price.toFixed(2) ?? "—"}
                </div>
              </div>
              <div style={{ marginTop: 12 }}>
                <div className="muted tiny">SOURCE</div>
                <div className={`badge ${forecast?.source === "live" ? "bull" : "neutral"}`}>
                  {forecast?.source ?? "—"}
                </div>
              </div>
            </div>
          </div>
        </div>

        <Kpi label="Mode" value={(health?.mode ?? "analysis").toUpperCase()} />
        <Kpi
          label="Live Trading"
          value={health?.live_trading_enabled ? "UNLOCKED" : "LOCKED"}
          tone={health?.live_trading_enabled ? "neg" : "pos"}
        />
        <Kpi
          label="Unrealised P&L"
          value={`₹ ${fmt(portfolio?.unrealized_pnl)}`}
          tone={(portfolio?.unrealized_pnl ?? 0) >= 0 ? "pos" : "neg"}
        />
        <Kpi
          label="Realised P&L (Today)"
          value={`₹ ${fmt(risk?.realised_pnl_today)}`}
          tone={(risk?.realised_pnl_today ?? 0) >= 0 ? "pos" : "neg"}
        />

        <div className="card half">
          <h3>NIFTY 50 SNAPSHOT</h3>
          <Row label="Index" value={forecast ? forecast.last_price.toFixed(2) : "—"} />
          <Row label="Bias (heuristic)" value={forecast?.bias ?? "—"} />
          <Row
            label="Display confidence"
            value={forecast ? `${(forecast.confidence * 100).toFixed(0)}%` : "—"}
          />
          <Row label="Source" value={forecast?.source ?? "—"} />
          <p className="muted tiny" style={{ marginTop: 10 }}>
            Regime classification (trending / range / volatile / quiet) will
            populate once live ticks are flowing through the candle builder.
            Bank Nifty is out of scope.
          </p>
        </div>

        <div className="card half">
          <h3>RISK BUDGET</h3>
          <Row label="Daily loss budget" value={`₹ ${fmt(risk?.daily_loss_budget)}`} />
          <Row
            label="Realised P&L today"
            value={`₹ ${fmt(risk?.realised_pnl_today)}`}
            tone={(risk?.realised_pnl_today ?? 0) >= 0 ? "pos" : "neg"}
          />
          <Row label="Trades today" value={String(risk?.trades_today ?? 0)} />
          <Row label="Open positions" value={String(risk?.open_positions ?? 0)} />
          <Row label="Consecutive losses" value={String(risk?.consecutive_losses ?? 0)} />
          <Row
            label="Kill switch"
            value={risk?.kill_switch ? "ENGAGED" : "OFF"}
            tone={risk?.kill_switch ? "neg" : "pos"}
          />
        </div>

        <div className="card two-thirds">
          <h3>CONNECTION HEALTH</h3>
          <Row label="Broker" value={health?.broker ?? "—"} />
          <Row
            label="WebSocket"
            value={health?.websocket?.connected ? "LIVE" : "OFFLINE"}
            tone={health?.websocket?.connected ? "pos" : "neg"}
          />
          <Row
            label="Tokens subscribed"
            value={String(health?.websocket?.tokens_subscribed ?? 0)}
          />
        </div>

        <div className="card third">
          <h3>HOW THIS WORKS</h3>
          <p className="small muted" style={{ lineHeight: 1.55 }}>
            The Nifty AI engine combines price action, indicators (EMA / VWAP /
            RSI / MACD / ATR), candle patterns, and the Nifty option chain to
            rank explainable signals. The forecast chart above is a
            transparent heuristic — swap it for a trained model by plugging
            into <code>strategy.forecaster</code>.
          </p>
        </div>
      </div>
    </div>
  );
}

function Kpi({ label, value, tone }: { label: string; value: string; tone?: "pos" | "neg" }) {
  return (
    <div className="card kpi">
      <h3>{label}</h3>
      <div className={`value ${tone ?? ""}`}>{value}</div>
    </div>
  );
}

function Row({ label, value, tone }: { label: string; value: string; tone?: "pos" | "neg" }) {
  return (
    <div className="row spread" style={{ padding: "4px 0" }}>
      <span className="muted small">{label}</span>
      <span
        className="mono"
        style={{
          color:
            tone === "pos" ? "var(--neon-green)" :
            tone === "neg" ? "var(--neon-red)"   : "var(--text)",
        }}
      >
        {value}
      </span>
    </div>
  );
}
