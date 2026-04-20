import { useEffect, useMemo, useState } from "react";
import { api, type SignalRow } from "../api";

const SETUP_CHIP: Record<string, string> = {
  MOMENTUM_BREAKOUT: "cyan",
  REVERSAL: "pink",
  TREND_CONTINUATION: "purple",
  BREAKOUT_PULLBACK: "cyan",
  RANGE_REVERSION: "amber",
};

function setupChipClass(setup: string): string {
  return SETUP_CHIP[setup?.toUpperCase() ?? ""] ?? "cyan";
}

export default function Signals() {
  const [rows, setRows] = useState<SignalRow[]>([]);
  const [filter, setFilter] = useState<"ALL" | "BULLISH" | "BEARISH" | "NEUTRAL">("ALL");
  const [form, setForm] = useState({
    strategy: "nifty_momentum_breakout",
    symbol: "NIFTY",
    direction: "BULLISH",
    entry: 22000,
    stop_loss: 21900,
    target1: 22200,
    confidence: 0.65,
  });

  async function refresh() {
    try {
      setRows(await api.signals(50));
    } catch {
      /* backend down */
    }
  }

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 3000);
    return () => clearInterval(t);
  }, []);

  async function submitSim(e: React.FormEvent) {
    e.preventDefault();
    await api.simSignal(form);
    refresh();
  }

  const visible = useMemo(
    () => (filter === "ALL" ? rows : rows.filter((r) => r.direction === filter)),
    [rows, filter],
  );

  const rr = useMemo(() => {
    const risk = Math.abs(form.entry - form.stop_loss);
    const reward = Math.abs(form.target1 - form.entry);
    return risk > 0 ? reward / risk : 0;
  }, [form.entry, form.stop_loss, form.target1]);

  return (
    <div className="grid">
      <div className="card hero glow">
        <div className="eyebrow">NIFTY 50 · AI SIGNAL ENGINE</div>
        <h1>Explainable setups · risk-sized · kill-switch guarded</h1>
        <div className="muted small" style={{ maxWidth: 720, marginTop: 6 }}>
          Every signal is scored transparently (regime alignment + indicator
          stack + RR). No claim of accuracy — see the{" "}
          <span className="chip amber">NOT FINANCIAL ADVICE</span> badge on each row.
        </div>
      </div>

      <div className="card half">
        <div className="row spread" style={{ marginBottom: 10 }}>
          <h3 style={{ margin: 0 }}>SIMULATE A SIGNAL</h3>
          <span className={`chip ${rr >= 1.5 ? "green" : rr >= 1.2 ? "amber" : "red"}`}>
            RR {rr.toFixed(2)}
          </span>
        </div>
        <form onSubmit={submitSim} className="col" style={{ gap: 10 }}>
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <input
              className="input"
              style={{ flex: "1 1 45%" }}
              value={form.strategy}
              onChange={(e) => setForm({ ...form, strategy: e.target.value })}
              placeholder="strategy"
            />
            <input
              className="input"
              style={{ flex: "1 1 45%" }}
              value={form.symbol}
              onChange={(e) => setForm({ ...form, symbol: e.target.value })}
              placeholder="symbol"
            />
          </div>
          <div className="segmented" style={{ alignSelf: "flex-start" }}>
            {(["BULLISH", "BEARISH", "NEUTRAL"] as const).map((d) => (
              <button
                key={d}
                type="button"
                className={form.direction === d ? "active" : ""}
                onClick={() => setForm({ ...form, direction: d })}
              >
                {d}
              </button>
            ))}
          </div>
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <NumField
              label="ENTRY"
              v={form.entry}
              on={(n) => setForm({ ...form, entry: n })}
            />
            <NumField
              label="STOP"
              v={form.stop_loss}
              on={(n) => setForm({ ...form, stop_loss: n })}
            />
            <NumField
              label="TARGET"
              v={form.target1}
              on={(n) => setForm({ ...form, target1: n })}
            />
          </div>
          <div className="col" style={{ gap: 4 }}>
            <div className="row spread">
              <span className="muted tiny">CONFIDENCE</span>
              <span className="mono tiny">{(form.confidence * 100).toFixed(0)}%</span>
            </div>
            <input
              type="range"
              min={0.1}
              max={0.99}
              step={0.01}
              value={form.confidence}
              onChange={(e) =>
                setForm({ ...form, confidence: parseFloat(e.target.value) })
              }
            />
            <div className="hbar">
              <span style={{ width: `${form.confidence * 100}%` }} />
            </div>
          </div>
          <button className="btn primary" type="submit">
            Generate signal
          </button>
        </form>
        <p className="muted tiny" style={{ marginTop: 10 }}>
          Simulated signals are logged, risk-checked, and (in paper mode) placed
          through the paper broker. Not a real live-trading instruction.
        </p>
      </div>

      <div className="card half">
        <h3>HOW SCORING WORKS</h3>
        <ul className="small muted" style={{ lineHeight: 1.7 }}>
          <li>Classifies regime: trending / range / volatile / quiet.</li>
          <li>Each strategy returns an explainable setup candidate.</li>
          <li>
            Score starts at strategy confidence, then: <span className="chip green">+0.15 regime aligns</span>{" "}
            <span className="chip cyan">+0.10 indicator stack</span>{" "}
            <span className="chip purple">+0.05 candle pattern</span>{" "}
            <span className="chip red">-0.20 RR&lt;1.3</span>.
          </li>
          <li>Never claims certainty. RR, invalidation, and reasons are shown per signal.</li>
        </ul>
      </div>

      <div className="card" style={{ gridColumn: "span 12" }}>
        <div className="row spread" style={{ marginBottom: 8, flexWrap: "wrap", gap: 8 }}>
          <h3 style={{ margin: 0 }}>RECENT SIGNALS</h3>
          <div className="segmented">
            {(["ALL", "BULLISH", "BEARISH", "NEUTRAL"] as const).map((d) => (
              <button
                key={d}
                type="button"
                className={filter === d ? "active" : ""}
                onClick={() => setFilter(d)}
              >
                {d}
              </button>
            ))}
          </div>
        </div>
        {visible.length === 0 ? (
          <div className="empty-state">
            <div className="glyph">✦</div>
            <div className="title">No signals match this filter</div>
            <div className="hint">
              Generate one above, connect a live feed, or clear the filter.
            </div>
          </div>
        ) : (
          <table className="glow-rows">
            <thead>
              <tr>
                <th>Time</th>
                <th>Strategy</th>
                <th>Symbol</th>
                <th>Direction</th>
                <th>Setup</th>
                <th>Entry</th>
                <th>SL</th>
                <th>T1</th>
                <th style={{ width: 120 }}>Confidence</th>
                <th>Regime</th>
                <th>Reasons</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((r) => (
                <tr key={r.id}>
                  <td className="mono tiny">
                    {new Date(r.ts).toLocaleTimeString()}
                  </td>
                  <td className="tiny muted">{r.strategy}</td>
                  <td className="mono">{r.symbol}</td>
                  <td>
                    <span
                      className={`chip ${
                        r.direction === "BULLISH"
                          ? "green"
                          : r.direction === "BEARISH"
                            ? "red"
                            : "amber"
                      }`}
                    >
                      {r.direction}
                    </span>
                  </td>
                  <td>
                    <span className={`chip ${setupChipClass(r.setup)}`}>
                      {r.setup}
                    </span>
                  </td>
                  <td className="mono">{r.entry}</td>
                  <td className="mono">{r.stop_loss}</td>
                  <td className="mono">{r.target1}</td>
                  <td style={{ minWidth: 110 }}>
                    <div className="hbar">
                      <span style={{ width: `${r.confidence * 100}%` }} />
                    </div>
                    <div className="mono tiny muted" style={{ marginTop: 2 }}>
                      {(r.confidence * 100).toFixed(0)}%
                    </div>
                  </td>
                  <td className="tiny">
                    <span className="chip">{r.regime}</span>
                  </td>
                  <td className="tiny muted">{r.reasons?.slice(0, 120)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="disclaimer">
        SCORING IS HEURISTIC · <strong>NOT A PREDICTION</strong> · Do not trade
        off a single signal without independent confirmation.
      </div>
    </div>
  );
}

function NumField({
  label,
  v,
  on,
}: {
  label: string;
  v: number;
  on: (n: number) => void;
}) {
  return (
    <label className="col" style={{ flex: "1 1 30%", gap: 4 }}>
      <span className="muted tiny">{label}</span>
      <input
        className="input mono"
        type="number"
        step="0.05"
        value={v}
        onChange={(e) => on(+e.target.value)}
      />
    </label>
  );
}
