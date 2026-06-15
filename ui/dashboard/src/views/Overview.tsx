import { useCallback } from "react";
import { api, ConfigResponse, RiskResponse, Signal } from "../api";
import { usePolling } from "../hooks/usePolling";

function StatCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="glass-card p-5">
      <p className="text-xs text-gray-500 uppercase tracking-wider">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${color || "text-white"}`}>{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </div>
  );
}

export default function Overview() {
  const configFetcher = useCallback(() => api.config(), []);
  const riskFetcher = useCallback(() => api.risk(), []);
  const signalFetcher = useCallback(() => api.latestSignal(), []);
  
  const { data: config } = usePolling<ConfigResponse>(configFetcher, 10000);
  const { data: risk } = usePolling<RiskResponse>(riskFetcher, 3000);
  const { data: signal } = usePolling<Signal | null>(signalFetcher, 3000);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Dashboard Overview</h2>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Capital"
          value={`₹${(config?.max_capital || 0).toLocaleString()}`}
        />
        <StatCard
          label="Daily P&L"
          value={`₹${(risk?.daily_pnl || 0).toFixed(2)}`}
          color={(risk?.daily_pnl || 0) >= 0 ? "text-neon-green" : "text-neon-red"}
        />
        <StatCard
          label="Can Trade"
          value={risk?.can_trade ? "YES" : "NO"}
          color={risk?.can_trade ? "text-neon-green" : "text-neon-red"}
          sub={risk?.reason}
        />
        <StatCard
          label="Kill Switch"
          value={risk?.kill_switch ? "ACTIVE" : "OFF"}
          color={risk?.kill_switch ? "text-neon-red" : "text-neon-green"}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="glass-card p-6">
          <h3 className="text-sm text-gray-400 mb-4">Latest AI Signal</h3>
          {signal ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-lg font-bold">{signal.instrument.tradingsymbol}</span>
                <span
                  className={`px-3 py-1 rounded-full text-xs font-semibold ${
                    signal.direction === "BULLISH"
                      ? "bg-neon-green/20 text-neon-green"
                      : signal.direction === "BEARISH"
                      ? "bg-neon-red/20 text-neon-red"
                      : "bg-gray-600/20 text-gray-400"
                  }`}
                >
                  {signal.direction}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-sm">
                <div>
                  <p className="text-gray-500 text-xs">Entry</p>
                  <p className="font-mono">{signal.entry}</p>
                </div>
                <div>
                  <p className="text-gray-500 text-xs">Stop Loss</p>
                  <p className="font-mono text-neon-red">{signal.stop_loss}</p>
                </div>
                <div>
                  <p className="text-gray-500 text-xs">Target</p>
                  <p className="font-mono text-neon-green">{signal.target1}</p>
                </div>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-500">
                  Confidence: <span className="text-neon-blue font-semibold">{(signal.confidence * 100).toFixed(1)}%</span>
                </span>
                <span className="text-gray-500">
                  RR: <span className="text-white">{signal.expected_rr}x</span>
                </span>
                <span className="text-gray-500">Regime: {signal.regime}</span>
              </div>
              <div className="text-xs text-gray-500">
                {signal.reasons.map((r, i) => (
                  <span key={i} className="inline-block mr-2 mb-1 px-2 py-0.5 bg-dark-700 rounded">
                    {r}
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-gray-600 text-sm">No signals yet — waiting for market data</p>
          )}
        </div>

        <div className="glass-card p-6">
          <h3 className="text-sm text-gray-400 mb-4">Configuration</h3>
          {config && (
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Mode</span>
                <span className="uppercase font-semibold">{config.trading_mode}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Risk/Trade</span>
                <span>{config.risk_per_trade_pct}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Max Daily Loss</span>
                <span className="text-neon-red">{config.max_daily_loss_pct}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Max Positions</span>
                <span>{config.max_open_positions}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Min Confidence</span>
                <span>{(config.min_signal_confidence * 100).toFixed(0)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Lot Size</span>
                <span>{config.default_lot_size}</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
