import type { RiskStatus } from "../api";

export default function RiskMonitor({ risk }: { risk: RiskStatus | null }) {
  if (!risk) return <div className="card">Loading risk status…</div>;
  const usedPct = Math.min(100, Math.max(0, (-risk.realised_pnl_today / Math.max(1, risk.daily_loss_budget)) * 100));
  return (
    <div className="grid">
      <div className="card two-thirds">
        <h3>Daily Loss Utilisation</h3>
        <div style={{ height: 14, border: "1px solid var(--panel-border)", borderRadius: 999, overflow: "hidden" }}>
          <div style={{
            width: `${usedPct}%`,
            height: "100%",
            background: "linear-gradient(90deg, var(--neon-green), var(--neon-amber), var(--neon-red))",
            boxShadow: "0 0 12px rgba(255,84,116,0.4)"
          }} />
        </div>
        <div className="row spread" style={{ marginTop: 8 }}>
          <span className="muted small">Realised today: ₹ {risk.realised_pnl_today.toLocaleString("en-IN")}</span>
          <span className="muted small">Budget: ₹ {risk.daily_loss_budget.toLocaleString("en-IN")}</span>
        </div>
      </div>
      <div className="card third">
        <h3>Guards</h3>
        <Row label="Kill switch" value={risk.kill_switch ? "ENGAGED" : "OFF"} tone={risk.kill_switch ? "neg" : "pos"} />
        <Row label="Live unlocked" value={risk.live_trading_enabled ? "YES" : "NO"} tone={risk.live_trading_enabled ? "neg" : "pos"} />
        <Row label="Mode" value={risk.app_mode.toUpperCase()} />
        <Row label="Within hours" value={risk.within_market_hours ? "YES" : "NO"} />
        <Row label="Past square-off" value={risk.past_square_off ? "YES" : "NO"} />
      </div>
      <div className="card half">
        <h3>Counters</h3>
        <Row label="Trades today" value={String(risk.trades_today)} />
        <Row label="Open positions" value={String(risk.open_positions)} />
        <Row label="Consecutive losses" value={String(risk.consecutive_losses)} />
      </div>
      <div className="card half">
        <h3>Rules</h3>
        <ul className="muted small" style={{ lineHeight: 1.6 }}>
          <li>Hard stop-loss mandatory on every trade.</li>
          <li>Max daily drawdown auto-locks new entries.</li>
          <li>Cooldown after N consecutive losses.</li>
          <li>Position size from capital risk % and SL distance.</li>
          <li>Slippage + flat brokerage modelled in P&L.</li>
          <li>Separate exposure caps for options buy / sell / futures / equity.</li>
        </ul>
      </div>
    </div>
  );
}

function Row({ label, value, tone }: { label: string; value: string; tone?: "pos" | "neg" }) {
  return (
    <div className="row spread" style={{ padding: "4px 0" }}>
      <span className="muted small">{label}</span>
      <span className="mono" style={{ color: tone === "pos" ? "var(--neon-green)" : tone === "neg" ? "var(--neon-red)" : "var(--text)" }}>
        {value}
      </span>
    </div>
  );
}
