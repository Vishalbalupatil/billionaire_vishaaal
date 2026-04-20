import { useEffect, useState } from "react";
import { api, type OrderRow, type TradeRow } from "../api";

export default function Trades() {
  const [orders, setOrders] = useState<OrderRow[]>([]);
  const [trades, setTrades] = useState<TradeRow[]>([]);

  useEffect(() => {
    async function refresh() {
      try {
        const [o, t] = await Promise.all([api.orders(50), api.trades(50)]);
        setOrders(o); setTrades(t);
      } catch { /* empty */ }
    }
    refresh();
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="grid">
      <div className="card half">
        <h3>Order Book</h3>
        <div className="scrollarea">
          <table>
            <thead>
              <tr><th>Time</th><th>Sym</th><th>Side</th><th>Qty</th><th>Type</th><th>Status</th><th>Broker</th></tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <td className="tiny mono">{new Date(o.ts).toLocaleTimeString()}</td>
                  <td>{o.symbol}</td>
                  <td><span className={`badge ${o.side === "BUY" ? "bull" : "bear"}`}>{o.side}</span></td>
                  <td className="mono">{o.qty}</td>
                  <td className="tiny">{o.order_type}</td>
                  <td className="tiny">{o.status}</td>
                  <td className="tiny muted">{o.broker}</td>
                </tr>
              ))}
              {orders.length === 0 && <tr><td colSpan={7} className="muted small">No orders yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      <div className="card half">
        <h3>Trade Blotter</h3>
        <div className="scrollarea">
          <table>
            <thead>
              <tr><th>Time</th><th>Sym</th><th>Side</th><th>Qty</th><th>Price</th><th>P&amp;L</th></tr>
            </thead>
            <tbody>
              {trades.map((t) => (
                <tr key={t.id}>
                  <td className="tiny mono">{new Date(t.ts).toLocaleTimeString()}</td>
                  <td>{t.symbol}</td>
                  <td><span className={`badge ${t.side === "BUY" ? "bull" : "bear"}`}>{t.side}</span></td>
                  <td className="mono">{t.qty}</td>
                  <td className="mono">{t.price.toFixed(2)}</td>
                  <td className="mono" style={{ color: t.pnl >= 0 ? "var(--neon-green)" : "var(--neon-red)" }}>
                    {t.pnl.toFixed(2)}
                  </td>
                </tr>
              ))}
              {trades.length === 0 && <tr><td colSpan={6} className="muted small">No trades yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
