import type { View } from "../App";

const items: { key: View; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "watchlist", label: "Watchlist" },
  { key: "signals", label: "AI Signals" },
  { key: "option", label: "Option Chain" },
  { key: "positions", label: "Positions" },
  { key: "trades", label: "Trade Blotter" },
  { key: "risk", label: "Risk Monitor" },
  { key: "alerts", label: "Alerts / Logs" },
  { key: "backtest", label: "Backtest" },
];

export default function Sidebar({
  view,
  onChange,
}: {
  view: View;
  onChange: (v: View) => void;
}) {
  return (
    <nav className="nav">
      {items.map((it) => (
        <button
          key={it.key}
          className={view === it.key ? "active" : ""}
          onClick={() => onChange(it.key)}
        >
          {it.label}
        </button>
      ))}
      <div style={{ marginTop: 28, padding: "12px", fontSize: 11, color: "var(--muted)", lineHeight: 1.5 }}>
        <div className="muted tiny">
          Decision-support only. <br /> Not financial advice.
        </div>
      </div>
    </nav>
  );
}
