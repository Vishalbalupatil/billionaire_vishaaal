import { useCallback } from "react";
import { api } from "../api";
import { usePolling } from "../hooks/usePolling";

export default function Positions() {
  const posFetcher = useCallback(() => api.positions(), []);
  const optPosFetcher = useCallback(() => api.optionsPositions(), []);
  const { data: positions } = usePolling<unknown[]>(posFetcher, 5000);
  const { data: optPositions } = usePolling<unknown[]>(optPosFetcher, 5000);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Positions</h2>

      <div className="glass-card p-5">
        <h3 className="text-sm text-gray-400 mb-4">Broker Positions</h3>
        {positions && positions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-gray-500 uppercase">
                <tr>
                  <th className="text-left pb-3">Symbol</th>
                  <th className="text-right pb-3">Qty</th>
                  <th className="text-right pb-3">Avg Price</th>
                  <th className="text-right pb-3">LTP</th>
                  <th className="text-right pb-3">P&L</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((p: any, i: number) => (
                  <tr key={i} className="border-t border-dark-600/30">
                    <td className="py-2 font-mono">{p.instrument?.tradingsymbol || "-"}</td>
                    <td className="py-2 text-right">{p.quantity}</td>
                    <td className="py-2 text-right font-mono">{p.avg_price?.toFixed(2)}</td>
                    <td className="py-2 text-right font-mono">{p.ltp?.toFixed(2)}</td>
                    <td className={`py-2 text-right font-mono font-semibold ${(p.pnl || 0) >= 0 ? "text-neon-green" : "text-neon-red"}`}>
                      ₹{(p.pnl || 0).toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-600 text-sm">No open positions</p>
        )}
      </div>

      <div className="glass-card p-5">
        <h3 className="text-sm text-gray-400 mb-4">Options Strategy Positions</h3>
        {optPositions && optPositions.length > 0 ? (
          <div className="space-y-3">
            {optPositions.map((op: any, i: number) => (
              <div key={i} className="bg-dark-700/50 rounded-xl p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-neon-blue">
                    {op.strategy?.strategy_type?.replace(/_/g, " ")}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    op.status === "OPEN" ? "bg-neon-green/20 text-neon-green" : "bg-gray-600/20 text-gray-400"
                  }`}>
                    {op.status}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <p className="text-gray-500">Entry Spot</p>
                    <p className="font-mono">{op.entry_spot?.toFixed(2)}</p>
                  </div>
                  <div>
                    <p className="text-gray-500">Current Spot</p>
                    <p className="font-mono">{op.current_spot?.toFixed(2)}</p>
                  </div>
                  <div>
                    <p className="text-gray-500">Unrealized P&L</p>
                    <p className={`font-mono font-semibold ${(op.unrealized_pnl || 0) >= 0 ? "text-neon-green" : "text-neon-red"}`}>
                      ₹{(op.unrealized_pnl || 0).toFixed(2)}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-600 text-sm">No active options strategies</p>
        )}
      </div>
    </div>
  );
}
