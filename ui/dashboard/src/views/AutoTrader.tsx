import { useCallback } from "react";
import { api, AutoTraderStatus, AutoTradeLogEntry } from "../api";
import { usePolling } from "../hooks/usePolling";

function actionColor(action: string): string {
  switch (action) {
    case "ENTER": return "bg-neon-green/20 text-neon-green";
    case "EXIT": return "bg-neon-blue/20 text-neon-blue";
    case "SIGNAL": return "bg-yellow-500/20 text-yellow-400";
    case "SKIP": return "bg-gray-600/20 text-gray-400";
    case "SCAN": return "bg-purple-500/20 text-purple-400";
    case "MONITOR": return "bg-cyan-500/20 text-cyan-400";
    default: return "bg-dark-600 text-gray-400";
  }
}

export default function AutoTrader() {
  const statusFetcher = useCallback(() => api.autoTraderStatus(), []);
  const logFetcher = useCallback(() => api.autoTraderLog(30), []);

  const { data: status } = usePolling<AutoTraderStatus>(statusFetcher, 3000);
  const { data: logs } = usePolling<AutoTradeLogEntry[]>(logFetcher, 3000);

  const activeTrades = status?.active_trades ? Object.values(status.active_trades) : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Auto Trader</h2>
        <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
          status?.active ? "bg-neon-green/20 text-neon-green" : "bg-gray-600/20 text-gray-400"
        }`}>
          {status?.active ? "ACTIVE" : "INACTIVE"}
        </span>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="glass-card p-4">
          <p className="text-xs text-gray-500 uppercase">Active Trades</p>
          <p className="text-2xl font-bold mt-1">{activeTrades.length}</p>
        </div>
        <div className="glass-card p-4">
          <p className="text-xs text-gray-500 uppercase">Scan Results</p>
          <p className="text-2xl font-bold mt-1">{status?.scan_results_count || 0}</p>
        </div>
        <div className="glass-card p-4">
          <p className="text-xs text-gray-500 uppercase">Patterns Found</p>
          <p className="text-2xl font-bold mt-1">{status?.patterns_count || 0}</p>
        </div>
        <div className="glass-card p-4">
          <p className="text-xs text-gray-500 uppercase">Symbols Tracked</p>
          <p className="text-2xl font-bold mt-1">{status?.trends_count || 0}</p>
        </div>
      </div>

      {/* Active Trades */}
      <div className="glass-card p-6">
        <h3 className="text-sm text-gray-400 mb-4">Active Trades</h3>
        {activeTrades.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-xs border-b border-dark-600">
                  <th className="text-left py-2 px-2">Symbol</th>
                  <th className="text-left py-2 px-2">Side</th>
                  <th className="text-right py-2 px-2">Qty</th>
                  <th className="text-right py-2 px-2">Entry</th>
                  <th className="text-right py-2 px-2">LTP</th>
                  <th className="text-right py-2 px-2">SL</th>
                  <th className="text-right py-2 px-2">Target</th>
                  <th className="text-right py-2 px-2">P&L</th>
                </tr>
              </thead>
              <tbody>
                {activeTrades.map((t, i) => (
                  <tr key={i} className="border-b border-dark-700/50">
                    <td className="py-2 px-2 font-semibold">{t.symbol}</td>
                    <td className="py-2 px-2">
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        t.side === "BUY" ? "bg-neon-green/20 text-neon-green" : "bg-neon-red/20 text-neon-red"
                      }`}>
                        {t.side}
                      </span>
                    </td>
                    <td className="py-2 px-2 text-right font-mono">{t.quantity}</td>
                    <td className="py-2 px-2 text-right font-mono">{t.entry.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono">{t.last_price.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono text-neon-red">{t.stop_loss.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono text-neon-green">{t.target.toFixed(2)}</td>
                    <td className={`py-2 px-2 text-right font-bold ${t.pnl >= 0 ? "text-neon-green" : "text-neon-red"}`}>
                      {t.pnl >= 0 ? "+" : ""}{t.pnl.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-600 text-sm">No active trades — auto-trader will enter when it finds high-confidence setups</p>
        )}
      </div>

      {/* Activity Log */}
      <div className="glass-card p-6">
        <h3 className="text-sm text-gray-400 mb-4">Activity Log</h3>
        {logs && logs.length > 0 ? (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {logs.slice().reverse().map((entry, i) => (
              <div key={i} className="flex items-start gap-3 py-2 border-b border-dark-700/30">
                <span className={`px-2 py-0.5 rounded text-xs shrink-0 ${actionColor(entry.action)}`}>
                  {entry.action}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm">{entry.symbol}</span>
                    {entry.pnl !== 0 && (
                      <span className={`text-xs font-mono ${entry.pnl >= 0 ? "text-neon-green" : "text-neon-red"}`}>
                        {entry.pnl >= 0 ? "+" : ""}₹{entry.pnl.toFixed(2)}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 truncate">{entry.details}</p>
                </div>
                <span className="text-xs text-gray-600 shrink-0">
                  {new Date(entry.ts).toLocaleTimeString()}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-600 text-sm">No activity yet — auto-trader will start logging when market opens</p>
        )}
      </div>
    </div>
  );
}
