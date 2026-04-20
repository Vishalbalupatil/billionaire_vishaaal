import type { HealthResp, PortfolioResp, RiskStatus } from "../api";

function fmt(n: number | undefined) {
  if (n === undefined || Number.isNaN(n)) return "—";
  const s = n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
  return s;
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
  return (
    <div>
      <div className="warn">
        This platform is a decision-support and execution tool. No profits are guaranteed. By default you are in
        <strong> {health?.mode ?? "analysis"} </strong> mode. Live trading requires an explicit config unlock.
      </div>

      <div className="grid">
        <Kpi label="Mode" value={(health?.mode ?? "analysis").toUpperCase()} />
        <Kpi label="Live Trading" value={health?.live_trading_enabled ? "UNLOCKED" : "LOCKED"} tone={health?.live_trading_enabled ? "neg" : "pos"} />
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
          <h3>Nifty / Bank Nifty Regime</h3>
          <div className="row spread">
            <div>
              <div className="mono small muted">NIFTY 50</div>
              <div className="value">—</div>
              <span className="badge neutral">AWAITING FEED</span>
            </div>
            <div>
              <div className="mono small muted">NIFTY BANK</div>
              <div className="value">—</div>
              <span className="badge neutral">AWAITING FEED</span>
            </div>
            <div>
              <div className="mono small muted">VIX</div>
              <div className="value">—</div>
            </div>
          </div>
          <p className="muted tiny">
            Connect Zerodha credentials and subscribe to NIFTY/BANKNIFTY tokens to see live regime (trending / range / volatile / quiet).
          </p>
        </div>

        <div className="card half">
          <h3>Risk Budget</h3>
          <Row label="Daily loss budget" value={`₹ ${fmt(risk?.daily_loss_budget)}`} />
          <Row label="Realised P&L today" value={`₹ ${fmt(risk?.realised_pnl_today)}`} tone={(risk?.realised_pnl_today ?? 0) >= 0 ? "pos" : "neg"} />
          <Row label="Trades today" value={String(risk?.trades_today ?? 0)} />
          <Row label="Open positions" value={String(risk?.open_positions ?? 0)} />
          <Row label="Consecutive losses" value={String(risk?.consecutive_losses ?? 0)} />
          <Row label="Kill switch" value={risk?.kill_switch ? "ENGAGED" : "OFF"} tone={risk?.kill_switch ? "neg" : "pos"} />
        </div>

        <div className="card two-thirds">
          <h3>Connection Health</h3>
          <Row label="Broker" value={health?.broker ?? "—"} />
          <Row label="WebSocket" value={health?.websocket?.connected ? "LIVE" : "OFFLINE"} tone={health?.websocket?.connected ? "pos" : "neg"} />
          <Row label="Tokens subscribed" value={String(health?.websocket?.tokens_subscribed ?? 0)} />
        </div>

        <div className="card third">
          <h3>AI Analysis (summary)</h3>
          <p className="small muted">
            The AI engine combines price action, indicators (EMA / VWAP / RSI / MACD / ATR / Supertrend),
            candle patterns, and option-chain analytics to produce a ranked, explainable signal list.
            Open <em>AI Signals</em> for the latest output.
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
      <span className={`mono ${tone === "pos" ? "" : tone === "neg" ? "" : ""}`}
            style={{ color: tone === "pos" ? "var(--neon-green)" : tone === "neg" ? "var(--neon-red)" : "var(--text)" }}>
        {value}
      </span>
    </div>
  );
}
