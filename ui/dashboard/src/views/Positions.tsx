import type { PortfolioResp } from "../api";
import Sparkline from "../components/Sparkline";

function fmt(n: number) {
  return n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

export default function Positions({ portfolio }: { portfolio: PortfolioResp | null }) {
  const positions = portfolio?.positions ?? [];
  const unrealised = portfolio?.unrealized_pnl ?? 0;

  return (
    <div className="grid">
      <div className="card hero glow">
        <div className="eyebrow">NIFTY 50 · LIVE POSITIONS</div>
        <h1>Book · {positions.length} open · ₹ {fmt(portfolio?.net_exposure ?? 0)} net</h1>
        <div className="muted small" style={{ maxWidth: 680, marginTop: 6 }}>
          Mark-to-market is driven by the paper broker when offline and by Zerodha
          LTP when ticks are flowing. P&amp;L here is unrealised — realised P&amp;L
          lives on the Trades view.
        </div>

        <div className="kpi-row" style={{ marginTop: 16 }}>
          <div className="stat">
            <div className="label">Open</div>
            <div className="big">{positions.length}</div>
          </div>
          <div className="stat pos">
            <div className="label">Long</div>
            <div className="big">{portfolio?.count_long ?? 0}</div>
          </div>
          <div className="stat neg">
            <div className="label">Short</div>
            <div className="big">{portfolio?.count_short ?? 0}</div>
          </div>
          <div className={`stat ${unrealised >= 0 ? "pos" : "neg"}`}>
            <div className="label">Unrealised P&amp;L</div>
            <div className="big">₹ {fmt(unrealised)}</div>
          </div>
        </div>
      </div>

      <div className="card" style={{ gridColumn: "span 12" }}>
        <div className="row spread" style={{ marginBottom: 8 }}>
          <h3 style={{ margin: 0 }}>OPEN POSITIONS</h3>
          <span className="muted tiny">auto-refresh · 1s</span>
        </div>

        {positions.length === 0 ? (
          <div className="empty-state">
            <div className="glyph">◎</div>
            <div className="title">No open positions</div>
            <div className="hint">
              Generate a signal from the AI Signals tab to open a paper trade,
              or wait for live signals to fire during market hours.
            </div>
          </div>
        ) : (
          <table className="glow-rows">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Side</th>
                <th style={{ width: 120 }}>Trend</th>
                <th>Qty</th>
                <th>Avg</th>
                <th>LTP</th>
                <th>Product</th>
                <th style={{ textAlign: "right" }}>Unrealised P&amp;L</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p, i) => {
                const pnl = (p.ltp - p.avg_price) * p.quantity;
                const side = p.quantity >= 0 ? "LONG" : "SHORT";
                const positive = pnl >= 0;
                return (
                  <tr key={i}>
                    <td className="mono">{p.instrument.tradingsymbol}</td>
                    <td>
                      <span className={`chip ${side === "LONG" ? "green" : "red"}`}>
                        {side}
                      </span>
                    </td>
                    <td>
                      <Sparkline
                        seed={`${p.instrument.tradingsymbol}-${side}`}
                        positive={positive}
                      />
                    </td>
                    <td className="mono">{Math.abs(p.quantity)}</td>
                    <td className="mono">{p.avg_price.toFixed(2)}</td>
                    <td className="mono">{p.ltp.toFixed(2)}</td>
                    <td>
                      <span className="chip">{p.product}</span>
                    </td>
                    <td
                      className="mono"
                      style={{
                        textAlign: "right",
                        color: positive ? "var(--neon-green)" : "var(--neon-red)",
                        textShadow: positive
                          ? "0 0 10px rgba(159,207,138,0.28)"
                          : "0 0 10px rgba(200,90,90,0.28)",
                      }}
                    >
                      ₹ {fmt(pnl)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="disclaimer">
        DECISION SUPPORT · <strong>NOT FINANCIAL ADVICE</strong> · Verify every
        position against your Zerodha console before acting.
      </div>
    </div>
  );
}
