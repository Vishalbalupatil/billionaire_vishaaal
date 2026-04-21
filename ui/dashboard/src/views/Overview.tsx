import { useEffect, useState } from "react";
import {
  api,
  type HealthResp,
  type ORBBacktestResp,
  type PortfolioResp,
  type RiskStatus,
} from "../api";
import ORBEquityChart from "../components/ORBEquityChart";

function fmt(n: number | undefined) {
  if (n === undefined || Number.isNaN(n)) return "—";
  return n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function fmtINR(n: number | undefined) {
  if (n === undefined || Number.isNaN(n)) return "—";
  const sign = n < 0 ? "-" : "";
  const v = Math.abs(n);
  if (v >= 1e7) return `${sign}₹${(v / 1e7).toFixed(2)}Cr`;
  if (v >= 1e5) return `${sign}₹${(v / 1e5).toFixed(2)}L`;
  if (v >= 1e3) return `${sign}₹${(v / 1e3).toFixed(1)}k`;
  return `${sign}₹${v.toFixed(0)}`;
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
  const [orb, setOrb] = useState<ORBBacktestResp | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancel = false;
    async function load() {
      try {
        const r = await api.orbBacktest();
        if (!cancel) {
          setOrb(r);
          setErr(null);
        }
      } catch (e) {
        if (!cancel) setErr(String(e));
      }
    }
    load();
    // Backtest is static; don't poll.
    return () => { cancel = true; };
  }, []);

  const m = orb?.metrics;
  const totalTone = (m?.total_pnl_rupees ?? 0) >= 0 ? "pos" : "neg";
  const isSynth = orb?.data_source === "synthetic";

  return (
    <div>
      <div className="grid">
        {/* HERO: ORB backtest summary */}
        <div className="card hero glow">
          <div className="eyebrow">NIFTY 50 · OPENING RANGE BREAKOUT (5m)</div>
          <h1>First 5-minute candle break → futures + ATM options</h1>
          <div className="muted small" style={{ maxWidth: 720 }}>
            Strategy: the 09:15–09:20 IST bar defines ORH / ORL. First touch of
            ORH ⇒ LONG current-month futures + BUY ATM call. First touch of ORL
            ⇒ SHORT futures + BUY ATM put. Stop = opposite end of the opening
            range. Target = 1:2 risk-reward. All positions squared off by
            15:15 IST. Options leg is Black-Scholes-approximated from India VIX
            (Kite doesn't retain historical option instrument masters).{" "}
            <strong style={{ color: "var(--neon-amber)" }}>Not financial advice.</strong>
            {isSynth && (
              <span style={{ color: "var(--neon-amber)", marginLeft: 6 }}>
                · SYNTHETIC DATA (run <code>python -m billionaire.cli backtest-orb --years 2</code> to replace)
              </span>
            )}
          </div>

          <div className="row spread" style={{ marginTop: 16, alignItems: "flex-start", gap: 18 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              {orb ? (
                <ORBEquityChart
                  combined={orb.equity_curve_combined}
                  futures={orb.equity_curve_futures}
                  options={orb.equity_curve_options}
                />
              ) : (
                <div className="chart-wrap" style={{ display: "grid", placeItems: "center" }}>
                  <span className="muted tiny">{err ?? "Loading backtest…"}</span>
                </div>
              )}
              <div className="row" style={{ gap: 16, marginTop: 8, fontSize: 11 }}>
                <LegendSwatch color="var(--neon-green, #3af58a)" label="Combined" />
                <LegendSwatch color="#67b3ff" label="Futures only" />
                <LegendSwatch color="#d6a3ff" label="Options only (BS)" />
              </div>
            </div>
            <div
              className="col"
              style={{
                flex: "0 0 220px", paddingLeft: 18,
                borderLeft: "1px dashed rgba(130,200,255,0.15)",
              }}
            >
              <div className="muted tiny">NET P&amp;L</div>
              <div className={`value mono ${totalTone}`} style={{ fontSize: 22 }}>
                {fmtINR(m?.total_pnl_rupees)}
              </div>
              <div className="muted tiny" style={{ marginTop: 10 }}>WIN RATE</div>
              <div className="mono" style={{ fontSize: 18 }}>
                {m ? `${m.win_rate_pct.toFixed(1)}%` : "—"}
              </div>
              <div className="muted tiny" style={{ marginTop: 10 }}>AVG R-MULTIPLE</div>
              <div className="mono" style={{ fontSize: 18 }}>
                {m ? m.avg_r_multiple.toFixed(2) : "—"}
              </div>
              <div className="muted tiny" style={{ marginTop: 10 }}>DATA</div>
              <div
                className={`badge ${orb?.data_source === "live-cache" ? "bull" : "neutral"}`}
                style={{ marginTop: 4 }}
              >
                {orb?.data_source ?? "—"}
              </div>
            </div>
          </div>
        </div>

        <Kpi label="Total Trades" value={String(m?.total_trades ?? 0)} />
        <Kpi
          label="Wins / Losses"
          value={m ? `${m.wins} / ${m.losses}` : "—"}
        />
        <Kpi
          label="Best Trade"
          value={fmtINR(m?.best_trade_rupees)}
          tone="pos"
        />
        <Kpi
          label="Worst Trade"
          value={fmtINR(m?.worst_trade_rupees)}
          tone="neg"
        />
        <Kpi
          label="Max Drawdown"
          value={fmtINR(m?.max_drawdown_rupees)}
          tone="neg"
        />
        <Kpi
          label="Sharpe (daily, ann.)"
          value={m ? m.sharpe_ratio.toFixed(2) : "—"}
        />
        <Kpi
          label="No-Trade Days"
          value={String(m?.no_trade_days ?? 0)}
        />
        <Kpi
          label="Options Contrib."
          value={fmtINR(m?.options_pnl_rupees)}
          tone={(m?.options_pnl_rupees ?? 0) >= 0 ? "pos" : "neg"}
        />

        <div className="card half">
          <h3>RECENT TRADES</h3>
          <div className="table-wrap" style={{ maxHeight: 320, overflowY: "auto" }}>
            <table className="table glow-rows">
              <thead>
                <tr>
                  <th>Date</th><th>Side</th><th>Entry</th><th>Exit</th>
                  <th>Why</th><th style={{ textAlign: "right" }}>P&amp;L</th>
                  <th style={{ textAlign: "right" }}>R</th>
                </tr>
              </thead>
              <tbody>
                {(orb?.trades ?? []).slice(-20).reverse().map((t) => (
                  <tr key={`${t.date}-${t.entry_ts}`}>
                    <td className="mono tiny">{t.date}</td>
                    <td>
                      <span className={`badge ${t.side === "LONG" ? "bull" : "bear"}`}>
                        {t.side}
                      </span>
                    </td>
                    <td className="mono tiny">{t.entry_price.toFixed(2)}</td>
                    <td className="mono tiny">{t.exit_price.toFixed(2)}</td>
                    <td className="tiny">{t.exit_reason}</td>
                    <td
                      className="mono tiny"
                      style={{
                        textAlign: "right",
                        color: t.combined_pnl_rupees >= 0 ? "var(--neon-green)" : "var(--neon-red)",
                      }}
                    >
                      {fmtINR(t.combined_pnl_rupees)}
                    </td>
                    <td
                      className="mono tiny"
                      style={{
                        textAlign: "right",
                        color: t.r_multiple >= 0 ? "var(--neon-green)" : "var(--neon-red)",
                      }}
                    >
                      {t.r_multiple.toFixed(2)}
                    </td>
                  </tr>
                ))}
                {(!orb || orb.trades.length === 0) && (
                  <tr>
                    <td colSpan={7} className="muted tiny" style={{ textAlign: "center", padding: 20 }}>
                      No trades yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card half">
          <h3>LIVE STATE</h3>
          <Row label="Mode" value={(health?.mode ?? "—").toUpperCase()} />
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
          <Row
            label="Unrealised P&L"
            value={`₹ ${fmt(portfolio?.unrealized_pnl)}`}
            tone={(portfolio?.unrealized_pnl ?? 0) >= 0 ? "pos" : "neg"}
          />
          <Row
            label="Realised P&L today"
            value={`₹ ${fmt(risk?.realised_pnl_today)}`}
            tone={(risk?.realised_pnl_today ?? 0) >= 0 ? "pos" : "neg"}
          />
          <Row
            label="Kill switch"
            value={risk?.kill_switch ? "ENGAGED" : "OFF"}
            tone={risk?.kill_switch ? "neg" : "pos"}
          />
        </div>

        <div className="card">
          <h3>HOW THE BACKTEST IS BUILT</h3>
          <p className="small muted" style={{ lineHeight: 1.55 }}>
            Futures leg fills on real 5-minute NIFTY-FUT bars pulled from Kite's
            historical_data endpoint, rolled to the front month each session.
            Entries fire at the first touch of ORH/ORL (not close-based —
            close-based misses ~40% of intraday moves). Options leg is
            approximated with Black-Scholes using the contemporaneous India VIX
            close as σ, 7.5% risk-free, 1.3% dividend, and the current month's
            last-Thursday expiry. ATM strike is selected at the moment of break.
            Fees of ₹40 per leg (~₹80 per leg-pair) are deducted.
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

function LegendSwatch({ color, label }: { color: string; label: string }) {
  return (
    <span className="row" style={{ gap: 6, alignItems: "center" }}>
      <span
        style={{
          width: 12, height: 12, borderRadius: 3, background: color,
          boxShadow: `0 0 8px ${color}`,
        }}
      />
      <span className="muted">{label}</span>
    </span>
  );
}
