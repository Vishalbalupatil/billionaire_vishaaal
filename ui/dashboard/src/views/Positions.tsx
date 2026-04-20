import type { PortfolioResp } from "../api";

export default function Positions({ portfolio }: { portfolio: PortfolioResp | null }) {
  const positions = portfolio?.positions ?? [];
  return (
    <div className="grid">
      <div className="card kpi"><h3>Open</h3><div className="value">{positions.length}</div></div>
      <div className="card kpi"><h3>Long</h3><div className="value pos">{portfolio?.count_long ?? 0}</div></div>
      <div className="card kpi"><h3>Short</h3><div className="value neg">{portfolio?.count_short ?? 0}</div></div>
      <div className="card kpi"><h3>Net Exposure</h3><div className="value">₹ {(portfolio?.net_exposure ?? 0).toLocaleString("en-IN")}</div></div>
      <div className="card" style={{ gridColumn: "span 12" }}>
        <h3>Positions</h3>
        <table>
          <thead>
            <tr><th>Symbol</th><th>Qty</th><th>Avg</th><th>LTP</th><th>Product</th><th>Unrealised P&amp;L</th></tr>
          </thead>
          <tbody>
            {positions.map((p, i) => {
              const pnl = (p.ltp - p.avg_price) * p.quantity;
              return (
                <tr key={i}>
                  <td>{p.instrument.tradingsymbol}</td>
                  <td className="mono">{p.quantity}</td>
                  <td className="mono">{p.avg_price.toFixed(2)}</td>
                  <td className="mono">{p.ltp.toFixed(2)}</td>
                  <td><span className="badge neutral">{p.product}</span></td>
                  <td className="mono" style={{ color: pnl >= 0 ? "var(--neon-green)" : "var(--neon-red)" }}>
                    ₹ {pnl.toFixed(2)}
                  </td>
                </tr>
              );
            })}
            {positions.length === 0 && (
              <tr><td colSpan={6} className="muted small">No open positions.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
