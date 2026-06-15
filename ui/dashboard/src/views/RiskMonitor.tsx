import { useCallback, useState } from "react";
import { api, RiskResponse, ConfigResponse } from "../api";
import { usePolling } from "../hooks/usePolling";

export default function RiskMonitor() {
  const riskFetcher = useCallback(() => api.risk(), []);
  const configFetcher = useCallback(() => api.config(), []);
  const { data: risk, refresh } = usePolling<RiskResponse>(riskFetcher, 3000);
  const { data: config } = usePolling<ConfigResponse>(configFetcher, 10000);
  const [toggling, setToggling] = useState(false);

  const toggleKillSwitch = async () => {
    if (!risk) return;
    setToggling(true);
    try {
      await api.killSwitch(!risk.kill_switch, risk.kill_switch ? "Manual deactivation" : "Manual activation");
      refresh();
    } finally {
      setToggling(false);
    }
  };

  const maxLoss = (config?.max_capital || 0) * ((config?.max_daily_loss_pct || 5) / 100);
  const lossUsed = risk ? Math.min(Math.abs(Math.min(risk.daily_pnl, 0)) / maxLoss * 100, 100) : 0;

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Risk Monitor</h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className={`glass-card p-6 text-center ${risk?.kill_switch ? "neon-glow-red" : "neon-glow-green"}`}>
          <p className="text-xs text-gray-500 uppercase mb-3">Kill Switch</p>
          <p className={`text-3xl font-bold ${risk?.kill_switch ? "text-neon-red" : "text-neon-green"}`}>
            {risk?.kill_switch ? "ACTIVE" : "OFF"}
          </p>
          <button
            onClick={toggleKillSwitch}
            disabled={toggling}
            className={`mt-4 px-6 py-2 rounded-xl text-sm font-semibold transition-all ${
              risk?.kill_switch
                ? "bg-neon-green/20 text-neon-green hover:bg-neon-green/30"
                : "bg-neon-red/20 text-neon-red hover:bg-neon-red/30"
            }`}
          >
            {risk?.kill_switch ? "Deactivate" : "Activate"}
          </button>
        </div>

        <div className="glass-card p-6">
          <p className="text-xs text-gray-500 uppercase mb-3">Daily P&L</p>
          <p className={`text-3xl font-bold font-mono ${(risk?.daily_pnl || 0) >= 0 ? "text-neon-green" : "text-neon-red"}`}>
            ₹{(risk?.daily_pnl || 0).toFixed(2)}
          </p>
          <div className="mt-4">
            <div className="flex justify-between text-xs text-gray-500 mb-1">
              <span>Loss Budget Used</span>
              <span>{lossUsed.toFixed(1)}%</span>
            </div>
            <div className="h-2 bg-dark-700 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  lossUsed > 80 ? "bg-neon-red" : lossUsed > 50 ? "bg-neon-yellow" : "bg-neon-green"
                }`}
                style={{ width: `${lossUsed}%` }}
              />
            </div>
            <p className="text-xs text-gray-600 mt-1">Max: ₹{maxLoss.toFixed(0)}</p>
          </div>
        </div>

        <div className="glass-card p-6">
          <p className="text-xs text-gray-500 uppercase mb-3">Trading Status</p>
          <p className={`text-xl font-bold ${risk?.can_trade ? "text-neon-green" : "text-neon-red"}`}>
            {risk?.can_trade ? "Active" : "Blocked"}
          </p>
          <p className="text-xs text-gray-500 mt-2">{risk?.reason}</p>
          {risk?.should_square_off && (
            <div className="mt-3 px-3 py-2 bg-neon-yellow/10 rounded-lg">
              <p className="text-xs text-neon-yellow font-semibold">Square-off time approaching</p>
            </div>
          )}
        </div>
      </div>

      <div className="glass-card p-6">
        <h3 className="text-sm text-gray-400 mb-4">Risk Parameters</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <p className="text-xs text-gray-500">Capital</p>
            <p className="font-mono">₹{(config?.max_capital || 0).toLocaleString()}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Risk/Trade</p>
            <p>{config?.risk_per_trade_pct}%</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Max Daily Loss</p>
            <p className="text-neon-red">{config?.max_daily_loss_pct}%</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Max Positions</p>
            <p>{config?.max_open_positions}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
