const rows = [
  { sym: "NIFTY 50", px: "—", chg: "—", badge: "neutral" as const, label: "AWAITING" },
  { sym: "NIFTY BANK", px: "—", chg: "—", badge: "neutral" as const, label: "AWAITING" },
  { sym: "RELIANCE", px: "—", chg: "—", badge: "neutral" as const, label: "AWAITING" },
  { sym: "HDFCBANK", px: "—", chg: "—", badge: "neutral" as const, label: "AWAITING" },
  { sym: "INFY", px: "—", chg: "—", badge: "neutral" as const, label: "AWAITING" },
  { sym: "TCS", px: "—", chg: "—", badge: "neutral" as const, label: "AWAITING" },
];

export default function Watchlist() {
  return (
    <div className="grid">
      <div className="card" style={{ gridColumn: "span 12" }}>
        <h3>Watchlist</h3>
        <table>
          <thead>
            <tr>
              <th>Symbol</th>
              <th>LTP</th>
              <th>Change</th>
              <th>Regime</th>
              <th>Top signal</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.sym}>
                <td>{r.sym}</td>
                <td className="mono">{r.px}</td>
                <td className="mono">{r.chg}</td>
                <td><span className={`badge ${r.badge}`}>{r.label}</span></td>
                <td className="muted small">—</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="muted tiny" style={{ marginTop: 10 }}>
          Populate <code>config/config.yaml</code> and connect Kite Connect to see live LTP, % change, regime classification,
          and the top AI signal per symbol.
        </p>
      </div>
    </div>
  );
}
