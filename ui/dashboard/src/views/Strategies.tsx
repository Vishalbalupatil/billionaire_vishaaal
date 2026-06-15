import { useCallback } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { api, Strategy } from "../api";
import { usePolling } from "../hooks/usePolling";

function PayoffChart({ payoff }: { payoff: { spot: number; pnl: number }[] }) {
  if (!payoff || payoff.length === 0) return null;

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={payoff} margin={{ top: 10, right: 10, left: 10, bottom: 10 }}>
        <XAxis
          dataKey="spot"
          tick={{ fontSize: 10, fill: "#666" }}
          tickFormatter={(v) => v.toFixed(0)}
        />
        <YAxis tick={{ fontSize: 10, fill: "#666" }} />
        <Tooltip
          contentStyle={{ background: "#1a1a2e", border: "1px solid #232340", borderRadius: 8 }}
          labelFormatter={(v) => `Spot: ${Number(v).toFixed(0)}`}
          formatter={(v: number) => [`₹${v.toFixed(2)}`, "P&L"]}
        />
        <ReferenceLine y={0} stroke="#666" strokeDasharray="3 3" />
        <Line
          type="monotone"
          dataKey="pnl"
          stroke="#00ff88"
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export default function Strategies() {
  const fetcher = useCallback(() => api.strategies(), []);
  const { data: strategies, loading } = usePolling<Strategy[]>(fetcher, 5000);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Options Strategies</h2>

      {loading && <p className="text-gray-500">Loading...</p>}

      {strategies && strategies.length === 0 && (
        <div className="glass-card p-8 text-center">
          <p className="text-gray-500">No strategies selected yet.</p>
          <p className="text-xs text-gray-600 mt-2">
            Strategies are auto-selected based on market regime + AI signal.
          </p>
        </div>
      )}

      <div className="space-y-4">
        {strategies?.map((s, i) => (
          <div key={i} className="glass-card p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-neon-blue">
                  {s.strategy_type.replace(/_/g, " ")}
                </h3>
                <p className="text-xs text-gray-500 mt-1">{s.reason}</p>
              </div>
              <span className="text-xs text-gray-500">
                Conf: {(s.confidence * 100).toFixed(0)}%
              </span>
            </div>

            <div className="grid grid-cols-4 gap-4 text-sm mb-4">
              <div>
                <p className="text-xs text-gray-500">Net Premium</p>
                <p className={`font-mono font-semibold ${s.net_premium >= 0 ? "text-neon-green" : "text-neon-red"}`}>
                  ₹{s.net_premium.toFixed(2)}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Max Profit</p>
                <p className="font-mono text-neon-green">₹{s.max_profit.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Max Loss</p>
                <p className="font-mono text-neon-red">₹{s.max_loss.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Breakeven</p>
                <p className="font-mono">{s.breakeven.map((b) => b.toFixed(0)).join(" / ")}</p>
              </div>
            </div>

            <div className="mb-4">
              <p className="text-xs text-gray-500 mb-2">Legs</p>
              <div className="grid grid-cols-4 gap-2">
                {s.legs.map((leg, j) => (
                  <div
                    key={j}
                    className={`p-2 rounded-lg text-xs text-center ${
                      leg.side === "BUY" ? "bg-neon-green/10 border border-neon-green/20" : "bg-neon-red/10 border border-neon-red/20"
                    }`}
                  >
                    <p className="font-semibold">{leg.side} {leg.option_type}</p>
                    <p className="font-mono">{leg.strike}</p>
                    <p className="text-gray-500">₹{leg.premium.toFixed(2)}</p>
                  </div>
                ))}
              </div>
            </div>

            <PayoffChart payoff={s.payoff} />
          </div>
        ))}
      </div>
    </div>
  );
}
