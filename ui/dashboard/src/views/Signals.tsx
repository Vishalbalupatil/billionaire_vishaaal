import { useEffect, useState } from "react";
import { api, type SignalRow } from "../api";

export default function Signals() {
  const [rows, setRows] = useState<SignalRow[]>([]);
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
    } catch { /* empty */ }
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

  return (
    <div className="grid">
      <div className="card half">
        <h3>Simulate a Signal</h3>
        <form onSubmit={submitSim} className="row" style={{ flexWrap: "wrap", gap: 8 }}>
          <input className="input" style={{ flex: "1 1 40%" }} value={form.strategy}
            onChange={(e) => setForm({ ...form, strategy: e.target.value })} placeholder="strategy" />
          <input className="input" style={{ flex: "1 1 40%" }} value={form.symbol}
            onChange={(e) => setForm({ ...form, symbol: e.target.value })} placeholder="symbol" />
          <select className="input" style={{ flex: "1 1 30%" }} value={form.direction}
            onChange={(e) => setForm({ ...form, direction: e.target.value })}>
            <option>BULLISH</option><option>BEARISH</option><option>NEUTRAL</option>
          </select>
          <input className="input" type="number" step="0.05" value={form.entry}
            onChange={(e) => setForm({ ...form, entry: +e.target.value })} placeholder="entry" />
          <input className="input" type="number" step="0.05" value={form.stop_loss}
            onChange={(e) => setForm({ ...form, stop_loss: +e.target.value })} placeholder="sl" />
          <input className="input" type="number" step="0.05" value={form.target1}
            onChange={(e) => setForm({ ...form, target1: +e.target.value })} placeholder="t1" />
          <input className="input" type="number" step="0.05" value={form.confidence}
            onChange={(e) => setForm({ ...form, confidence: +e.target.value })} placeholder="confidence" />
          <button className="btn primary" type="submit">Generate</button>
        </form>
        <p className="muted tiny" style={{ marginTop: 8 }}>
          Simulated signals are logged, risk-checked, and (in paper mode) placed through the paper broker.
        </p>
      </div>

      <div className="card half">
        <h3>How the AI Signal Engine Works</h3>
        <ul className="small muted" style={{ lineHeight: 1.6 }}>
          <li>Classifies regime: trending / range / volatile / quiet.</li>
          <li>Runs every registered strategy; each returns an explainable setup.</li>
          <li>Score starts at strategy confidence, then:
            <br /> +0.15 if regime aligns · +0.10 indicator stack agrees · +0.05 candle pattern agrees · −0.20 RR&lt;1.3.</li>
          <li>Never claims certainty. RR, invalidation, and reasons are shown for every signal.</li>
        </ul>
      </div>

      <div className="card" style={{ gridColumn: "span 12" }}>
        <h3>Recent Signals</h3>
        <table>
          <thead>
            <tr>
              <th>Time</th><th>Strategy</th><th>Symbol</th><th>Dir</th><th>Setup</th>
              <th>Entry</th><th>SL</th><th>T1</th><th>Conf</th><th>Regime</th><th>Reasons</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td className="mono tiny">{new Date(r.ts).toLocaleTimeString()}</td>
                <td className="tiny">{r.strategy}</td>
                <td className="mono">{r.symbol}</td>
                <td>
                  <span className={`badge ${r.direction === "BULLISH" ? "bull" : r.direction === "BEARISH" ? "bear" : "neutral"}`}>
                    {r.direction}
                  </span>
                </td>
                <td className="tiny">{r.setup}</td>
                <td className="mono">{r.entry}</td>
                <td className="mono">{r.stop_loss}</td>
                <td className="mono">{r.target1}</td>
                <td className="mono">{(r.confidence * 100).toFixed(0)}%</td>
                <td className="tiny muted">{r.regime}</td>
                <td className="tiny muted">{r.reasons?.slice(0, 120)}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={11} className="muted small">No signals yet. Generate one above or connect a live feed.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
