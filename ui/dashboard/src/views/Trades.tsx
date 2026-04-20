import { useEffect, useMemo, useState } from "react";
import { api, type OrderRow, type TradeRow } from "../api";

function fmt(n: number) {
  return n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function timelineClass(status: string): string {
  const s = status.toUpperCase();
  if (s === "COMPLETE" || s === "FILLED") return "ok";
  if (s === "REJECTED" || s === "CANCELLED" || s === "FAILED") return "err";
  if (s === "OPEN" || s === "PENDING") return "warn";
  return "";
}

export default function Trades() {
  const [orders, setOrders] = useState<OrderRow[]>([]);
  const [trades, setTrades] = useState<TradeRow[]>([]);

  useEffect(() => {
    async function refresh() {
      try {
        const [o, t] = await Promise.all([api.orders(50), api.trades(50)]);
        setOrders(o);
        setTrades(t);
      } catch {
        /* backend down */
      }
    }
    refresh();
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, []);

  const stats = useMemo(() => {
    const realised = trades.reduce((a, t) => a + t.pnl, 0);
    const wins = trades.filter((t) => t.pnl > 0).length;
    const losses = trades.filter((t) => t.pnl < 0).length;
    return { realised, wins, losses, total: trades.length };
  }, [trades]);

  return (
    <div className="grid">
      <div className="card hero glow">
        <div className="eyebrow">NIFTY 50 · EXECUTION LOG</div>
        <h1>Orders &amp; trades · {orders.length} orders · {trades.length} fills</h1>
        <div className="muted small" style={{ maxWidth: 680, marginTop: 6 }}>
          Every order flows through the risk gate, the kill switch, and the
          duplicate guard before hitting the broker. Paper fills model 5 bps
          slippage and flat brokerage.
        </div>

        <div className="kpi-row" style={{ marginTop: 16 }}>
          <div className={`stat ${stats.realised >= 0 ? "pos" : "neg"}`}>
            <div className="label">Realised P&amp;L</div>
            <div className="big">₹ {fmt(stats.realised)}</div>
          </div>
          <div className="stat pos">
            <div className="label">Wins</div>
            <div className="big">{stats.wins}</div>
          </div>
          <div className="stat neg">
            <div className="label">Losses</div>
            <div className="big">{stats.losses}</div>
          </div>
          <div className="stat">
            <div className="label">Fills</div>
            <div className="big">{stats.total}</div>
          </div>
        </div>
      </div>

      <div className="card half">
        <div className="row spread" style={{ marginBottom: 8 }}>
          <h3 style={{ margin: 0 }}>ORDER BOOK</h3>
          <span className="muted tiny">latest 50 · 3s refresh</span>
        </div>
        {orders.length === 0 ? (
          <div className="empty-state">
            <div className="glyph">⟳</div>
            <div className="title">No orders yet</div>
            <div className="hint">
              Orders placed via the paper broker (or Zerodha in live mode) will
              appear here in real time.
            </div>
          </div>
        ) : (
          <div className="timeline" style={{ maxHeight: 340, overflowY: "auto" }}>
            {orders.map((o) => (
              <div key={o.id} className={`item ${timelineClass(o.status)}`}>
                <div>
                  <span className="ts">{new Date(o.ts).toLocaleTimeString()}</span>
                  <span className="msg">
                    <span className={`chip ${o.side === "BUY" ? "green" : "red"}`}>
                      {o.side}
                    </span>{" "}
                    <span className="mono">{o.symbol}</span>{" "}
                    <span className="mono muted">×{o.qty}</span>{" "}
                    <span className="chip">{o.order_type}</span>
                  </span>
                </div>
                <div className="sub">
                  {o.status} · {o.broker} · avg {o.avg_price?.toFixed(2) ?? "—"}
                  {o.tag ? ` · ${o.tag}` : ""}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card half">
        <div className="row spread" style={{ marginBottom: 8 }}>
          <h3 style={{ margin: 0 }}>TRADE BLOTTER</h3>
          <span className="muted tiny">last 50 fills</span>
        </div>
        {trades.length === 0 ? (
          <div className="empty-state">
            <div className="glyph">◆</div>
            <div className="title">No fills yet</div>
            <div className="hint">
              Closed trades and realised P&amp;L show up here as positions exit.
            </div>
          </div>
        ) : (
          <table className="glow-rows">
            <thead>
              <tr>
                <th>Time</th>
                <th>Symbol</th>
                <th>Side</th>
                <th>Qty</th>
                <th>Price</th>
                <th style={{ textAlign: "right" }}>P&amp;L</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((t) => (
                <tr key={t.id}>
                  <td className="tiny mono">{new Date(t.ts).toLocaleTimeString()}</td>
                  <td className="mono">{t.symbol}</td>
                  <td>
                    <span className={`chip ${t.side === "BUY" ? "green" : "red"}`}>
                      {t.side}
                    </span>
                  </td>
                  <td className="mono">{t.qty}</td>
                  <td className="mono">{t.price.toFixed(2)}</td>
                  <td
                    className="mono"
                    style={{
                      textAlign: "right",
                      color: t.pnl >= 0 ? "var(--neon-green)" : "var(--neon-red)",
                    }}
                  >
                    {t.pnl >= 0 ? "+" : ""}
                    {t.pnl.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="disclaimer">
        EXECUTION LOG · <strong>VERIFY AGAINST ZERODHA CONSOLE</strong> ·
        Synthetic broker fills are clearly marked in the broker column.
      </div>
    </div>
  );
}
