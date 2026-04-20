import type { View } from "../App";

const groups: { label: string; items: { key: View; label: string; emoji: string }[] }[] = [
  {
    label: "AI",
    items: [
      { key: "overview", label: "Overview",   emoji: "◉" },
      { key: "forecast", label: "Forecast",   emoji: "✦" },
      { key: "signals",  label: "Signals",    emoji: "∿" },
    ],
  },
  {
    label: "TRADING",
    items: [
      { key: "watchlist", label: "Watchlist", emoji: "≋" },
      { key: "positions", label: "Positions", emoji: "◎" },
      { key: "trades",    label: "Trades",    emoji: "→" },
      { key: "option",    label: "Options",   emoji: "◇" },
    ],
  },
  {
    label: "OPS",
    items: [
      { key: "risk",     label: "Risk",     emoji: "◆" },
      { key: "alerts",   label: "Alerts",   emoji: "!" },
      { key: "backtest", label: "Backtest", emoji: "↻" },
    ],
  },
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
      {groups.map((g) => (
        <div key={g.label}>
          <div className="group-label">{g.label}</div>
          {g.items.map((it) => (
            <button
              key={it.key}
              className={view === it.key ? "active" : ""}
              onClick={() => onChange(it.key)}
            >
              <span className="nav-icon" style={{ fontSize: 14 }}>{it.emoji}</span>
              {it.label}
            </button>
          ))}
        </div>
      ))}
      <div style={{ marginTop: 24, padding: "12px", lineHeight: 1.5 }}>
        <div className="muted tiny">
          Nifty 50 only.<br />
          Decision-support.<br />
          Not financial advice.
        </div>
      </div>
    </nav>
  );
}
