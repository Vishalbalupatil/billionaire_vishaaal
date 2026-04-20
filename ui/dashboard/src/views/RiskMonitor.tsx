import type { RiskStatus } from "../api";

function fmt(n: number) {
  return n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

export default function RiskMonitor({ risk }: { risk: RiskStatus | null }) {
  if (!risk) {
    return (
      <div className="grid">
        <div className="card hero glow">
          <div className="eyebrow">NIFTY 50 · RISK MONITOR</div>
          <h1>Loading…</h1>
        </div>
      </div>
    );
  }

  const lossPct =
    (-risk.realised_pnl_today / Math.max(1, risk.daily_loss_budget)) * 100;
  const usedPct = Math.min(100, Math.max(0, lossPct));

  return (
    <div className="grid">
      <div className="card hero glow">
        <div className="eyebrow">NIFTY 50 · RISK MONITOR</div>
        <h1>Capital guards · {risk.app_mode.toUpperCase()}</h1>
        <div className="muted small" style={{ maxWidth: 680, marginTop: 6 }}>
          Pre-trade gates enforce stop-loss, exposure caps, consecutive-loss
          cooldowns, and daily drawdown. The kill switch is a master-off; every
          order checks it before hitting the broker.
        </div>
      </div>

      <div className="card two-thirds">
        <div className="row spread" style={{ marginBottom: 10 }}>
          <h3 style={{ margin: 0 }}>DAILY LOSS UTILISATION</h3>
          <span
            className={`chip ${
              usedPct >= 80 ? "red" : usedPct >= 50 ? "amber" : "green"
            }`}
          >
            {usedPct.toFixed(0)}% used
          </span>
        </div>
        <div className="row" style={{ gap: 18, alignItems: "center" }}>
          <RingGauge pct={usedPct} />
          <div className="col" style={{ flex: 1, gap: 12 }}>
            <div className="hbar warn">
              <span style={{ width: `${usedPct}%` }} />
            </div>
            <div className="row spread">
              <div className="col" style={{ gap: 2 }}>
                <span className="muted tiny">REALISED TODAY</span>
                <span
                  className="mono"
                  style={{
                    fontSize: 16,
                    color:
                      risk.realised_pnl_today >= 0
                        ? "var(--neon-green)"
                        : "var(--neon-red)",
                  }}
                >
                  ₹ {fmt(risk.realised_pnl_today)}
                </span>
              </div>
              <div className="col" style={{ gap: 2, alignItems: "flex-end" }}>
                <span className="muted tiny">DAILY LOSS BUDGET</span>
                <span className="mono" style={{ fontSize: 16 }}>
                  ₹ {fmt(risk.daily_loss_budget)}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="card third">
        <h3>GUARDS</h3>
        <Row
          label="Kill switch"
          value={risk.kill_switch ? "ENGAGED" : "OFF"}
          chip={risk.kill_switch ? "red" : "green"}
        />
        <Row
          label="Live unlocked"
          value={risk.live_trading_enabled ? "YES" : "NO"}
          chip={risk.live_trading_enabled ? "red" : "green"}
        />
        <Row
          label="Mode"
          value={risk.app_mode.toUpperCase()}
          chip={
            risk.app_mode === "live"
              ? "red"
              : risk.app_mode === "paper"
                ? "amber"
                : "cyan"
          }
        />
        <Row
          label="Within market hours"
          value={risk.within_market_hours ? "YES" : "NO"}
          chip={risk.within_market_hours ? "green" : ""}
        />
        <Row
          label="Past square-off"
          value={risk.past_square_off ? "YES" : "NO"}
          chip={risk.past_square_off ? "amber" : ""}
        />
      </div>

      <div className="card half">
        <h3>COUNTERS</h3>
        <div className="kpi-row">
          <div className="stat">
            <div className="label">Trades today</div>
            <div className="big">{risk.trades_today}</div>
          </div>
          <div className="stat">
            <div className="label">Open positions</div>
            <div className="big">{risk.open_positions}</div>
          </div>
          <div className={`stat ${risk.consecutive_losses > 0 ? "neg" : ""}`}>
            <div className="label">Consec. losses</div>
            <div className="big">{risk.consecutive_losses}</div>
          </div>
          <div className="stat">
            <div className="label">Slippage</div>
            <div className="big">5 bps</div>
          </div>
        </div>
      </div>

      <div className="card half">
        <h3>RULES ENFORCED</h3>
        <ul className="muted small" style={{ lineHeight: 1.7 }}>
          <li>
            <span className="chip red">HARD</span> Stop-loss mandatory on every trade.
          </li>
          <li>
            <span className="chip red">HARD</span> Max daily drawdown auto-locks
            new entries.
          </li>
          <li>
            <span className="chip amber">SOFT</span> Cooldown after N consecutive
            losses.
          </li>
          <li>
            <span className="chip cyan">RISK</span> Position size from capital
            risk % and SL distance.
          </li>
          <li>
            <span className="chip cyan">MODEL</span> Slippage + flat brokerage
            modelled in P&amp;L.
          </li>
          <li>
            <span className="chip purple">CAPS</span> Separate exposure caps
            per options-buy / options-sell / futures / equity.
          </li>
        </ul>
      </div>

      <div className="disclaimer">
        RISK GATES · <strong>NOT A PROFIT GUARANTEE</strong> · Guards reduce tail
        risk, they do not eliminate it.
      </div>
    </div>
  );
}

function Row({
  label,
  value,
  chip,
}: {
  label: string;
  value: string;
  chip?: string;
}) {
  return (
    <div
      className="row spread"
      style={{
        padding: "8px 0",
        borderBottom: "1px dashed rgba(130,200,255,0.06)",
      }}
    >
      <span className="muted small">{label}</span>
      <span className={`chip ${chip ?? ""}`}>{value}</span>
    </div>
  );
}

function RingGauge({ pct }: { pct: number }) {
  const r = 62;
  const c = 2 * Math.PI * r;
  const dash = (pct / 100) * c;
  const color =
    pct >= 80 ? "#ff5474" : pct >= 50 ? "#ffd36b" : "#6bff9e";
  return (
    <div className="ring-wrap">
      <svg width="160" height="160" viewBox="0 0 160 160">
        <circle
          cx="80"
          cy="80"
          r={r}
          fill="none"
          stroke="rgba(130,200,255,0.10)"
          strokeWidth="10"
        />
        <circle
          cx="80"
          cy="80"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeDasharray={`${dash} ${c - dash}`}
          strokeDashoffset={0}
          strokeLinecap="round"
          transform="rotate(-90 80 80)"
          style={{ filter: `drop-shadow(0 0 6px ${color})` }}
        />
      </svg>
      <div className="ring-label">
        <div>
          <div className="big" style={{ color }}>
            {pct.toFixed(0)}%
          </div>
          <div className="sub">of daily budget</div>
        </div>
      </div>
    </div>
  );
}
