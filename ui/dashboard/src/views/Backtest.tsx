/**
 * Backtest view — visual summary of a backtest report.
 *
 * Until the backend exposes ``/api/backtest/report`` we render the layout
 * against a deterministic synthetic equity curve so the UI stays legible
 * offline. The CLI command to regenerate real data is shown prominently.
 */

import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

function mulberry32(a: number) {
  return function () {
    let t = (a += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

interface Point {
  i: number;
  equity: number;
  dd: number;
}

function buildEquity(bars: number, seed: number): Point[] {
  const rand = mulberry32(seed);
  let eq = 100_000;
  let peak = eq;
  const out: Point[] = [];
  for (let i = 0; i < bars; i++) {
    const step = (rand() - 0.47) * 1400;
    eq += step;
    peak = Math.max(peak, eq);
    const dd = (eq - peak) / peak;
    out.push({ i, equity: Math.round(eq), dd });
  }
  return out;
}

function metrics(points: Point[]) {
  if (points.length === 0) {
    return { cagr: 0, sharpe: 0, maxDD: 0, winRate: 0, trades: 0, pf: 0 };
  }
  const start = points[0].equity;
  const end = points[points.length - 1].equity;
  const ret = (end - start) / start;
  const steps = points.length;
  const cagr = (Math.pow(1 + ret, 250 / Math.max(1, steps)) - 1) * 100;
  const returns = points
    .slice(1)
    .map((p, idx) => (p.equity - points[idx].equity) / points[idx].equity);
  const mean = returns.reduce((a, b) => a + b, 0) / Math.max(1, returns.length);
  const variance =
    returns.reduce((a, b) => a + (b - mean) ** 2, 0) /
    Math.max(1, returns.length);
  const sharpe = variance > 0 ? (mean / Math.sqrt(variance)) * Math.sqrt(250) : 0;
  const maxDD = Math.min(...points.map((p) => p.dd)) * 100;
  return {
    cagr,
    sharpe,
    maxDD,
    winRate: 54,
    trades: 83,
    pf: 1.42,
  };
}

function fmt(n: number) {
  return n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

export default function Backtest() {
  const [bars, setBars] = useState<500 | 1000 | 1500>(1000);
  const points = useMemo(() => buildEquity(bars, 42), [bars]);
  const m = useMemo(() => metrics(points), [points]);

  const sampleTrades = useMemo(() => {
    const rand = mulberry32(7);
    const symbols = ["NIFTY", "RELIANCE", "HDFCBANK", "INFY", "TCS", "ICICIBANK"];
    return Array.from({ length: 8 }).map((_, i) => {
      const s = symbols[i % symbols.length];
      const pnl = (rand() - 0.4) * 2400;
      const side = rand() > 0.5 ? "LONG" : "SHORT";
      return { i, s, side, pnl };
    });
  }, []);

  return (
    <div className="grid">
      <div className="card hero glow">
        <div className="eyebrow">NIFTY 50 · BACKTEST</div>
        <h1>Bar-by-bar replay · same engine as live</h1>
        <div className="muted small" style={{ maxWidth: 720, marginTop: 6 }}>
          Runs the production SignalEngine + PaperBroker over historical bars.
          The numbers below are a{" "}
          <span className="chip amber">SCAFFOLD REPORT</span> rendered off a
          deterministic equity curve so you can see the layout.
        </div>

        <div className="row tag-row" style={{ marginTop: 14 }}>
          <div className="segmented">
            {([500, 1000, 1500] as const).map((b) => (
              <button
                key={b}
                className={bars === b ? "active" : ""}
                onClick={() => setBars(b)}
              >
                {b} bars
              </button>
            ))}
          </div>
          <code className="tiny muted" style={{ marginLeft: "auto" }}>
            $ billionaire backtest --symbol NIFTY --bars {bars}
          </code>
        </div>
      </div>

      <div className="card two-thirds">
        <div className="row spread" style={{ marginBottom: 8 }}>
          <h3 style={{ margin: 0 }}>EQUITY CURVE</h3>
          <span className="muted tiny">starting capital ₹ 1,00,000</span>
        </div>
        <div style={{ width: "100%", height: 280 }}>
          <ResponsiveContainer>
            <AreaChart
              data={points}
              margin={{ top: 12, right: 18, left: 6, bottom: 0 }}
            >
              <defs>
                <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#39e3ff" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#39e3ff" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid
                stroke="rgba(130,200,255,0.08)"
                strokeDasharray="3 3"
                vertical={false}
              />
              <XAxis
                dataKey="i"
                tick={{ fill: "#556079", fontSize: 10 }}
                axisLine={{ stroke: "rgba(130,200,255,0.15)" }}
                tickLine={false}
              />
              <YAxis
                domain={["dataMin - 1000", "dataMax + 1000"]}
                tick={{ fill: "#556079", fontSize: 10 }}
                axisLine={{ stroke: "rgba(130,200,255,0.15)" }}
                tickLine={false}
                width={64}
                tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`}
              />
              <Tooltip
                contentStyle={{
                  background: "rgba(6,9,20,0.95)",
                  border: "1px solid rgba(57,227,255,0.35)",
                  borderRadius: 8,
                  fontFamily: "JetBrains Mono",
                }}
                labelStyle={{ color: "#7a88a8" }}
                formatter={(v) => [`₹ ${fmt(Number(v))}`, "Equity"]}
              />
              <Area
                type="monotone"
                dataKey="equity"
                stroke="#39e3ff"
                strokeWidth={1.8}
                fill="url(#eqGrad)"
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card third">
        <h3>METRICS</h3>
        <div className="kpi-row">
          <div className={`stat ${m.cagr >= 0 ? "pos" : "neg"}`}>
            <div className="label">CAGR</div>
            <div className="big">{m.cagr.toFixed(1)}%</div>
          </div>
          <div className={`stat ${m.sharpe >= 1 ? "pos" : "neg"}`}>
            <div className="label">Sharpe*</div>
            <div className="big">{m.sharpe.toFixed(2)}</div>
          </div>
          <div className="stat neg">
            <div className="label">Max DD</div>
            <div className="big">{m.maxDD.toFixed(1)}%</div>
          </div>
          <div className="stat">
            <div className="label">Win rate</div>
            <div className="big">{m.winRate}%</div>
          </div>
          <div className="stat">
            <div className="label">Trades</div>
            <div className="big">{m.trades}</div>
          </div>
          <div className="stat">
            <div className="label">Profit factor</div>
            <div className="big">{m.pf.toFixed(2)}</div>
          </div>
        </div>
        <p className="muted tiny" style={{ marginTop: 8 }}>
          * Sharpe is a 250-bar proxy. Real report uses daily-returns.
        </p>
      </div>

      <div className="card half">
        <div className="row spread" style={{ marginBottom: 8 }}>
          <h3 style={{ margin: 0 }}>SAMPLE TRADES</h3>
          <span className="muted tiny">top contributors</span>
        </div>
        <table className="glow-rows">
          <thead>
            <tr>
              <th>#</th>
              <th>Symbol</th>
              <th>Side</th>
              <th style={{ textAlign: "right" }}>P&amp;L</th>
            </tr>
          </thead>
          <tbody>
            {sampleTrades.map((t, i) => (
              <tr key={i}>
                <td className="mono tiny muted">{i + 1}</td>
                <td className="mono">{t.s}</td>
                <td>
                  <span
                    className={`chip ${t.side === "LONG" ? "green" : "red"}`}
                  >
                    {t.side}
                  </span>
                </td>
                <td
                  className="mono"
                  style={{
                    textAlign: "right",
                    color: t.pnl >= 0 ? "var(--neon-green)" : "var(--neon-red)",
                  }}
                >
                  {t.pnl >= 0 ? "+" : ""}₹ {fmt(t.pnl)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card half">
        <h3>HOW IT RUNS</h3>
        <ul className="muted small" style={{ lineHeight: 1.8 }}>
          <li>
            <span className="chip cyan">CLI</span> <code>make backtest</code> or{" "}
            <code>billionaire backtest --symbol NIFTY --bars 1500</code>
          </li>
          <li>
            <span className="chip purple">ENGINE</span> same SignalEngine +
            PaperBroker as live — zero drift between test and prod
          </li>
          <li>
            <span className="chip amber">DATA</span> synthetic by default;
            wire in Zerodha historical REST for real bars
          </li>
          <li>
            <span className="chip green">REPORT</span> JSON at{" "}
            <code>data/sample_backtest_report.json</code> with per-trade,
            per-strategy, and equity curve
          </li>
        </ul>
      </div>

      <div className="disclaimer">
        BACKTEST ≠ PERFORMANCE · <strong>NOT PREDICTIVE</strong> · Past results
        don't carry forward. Overfitting kills accounts.
      </div>
    </div>
  );
}
