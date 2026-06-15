import { useCallback } from "react";
import { api, Signal } from "../api";
import { usePolling } from "../hooks/usePolling";

export default function Signals() {
  const fetcher = useCallback(() => api.signals(), []);
  const { data: signals, loading } = usePolling<Signal[]>(fetcher, 5000);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">AI Signals</h2>

      {loading && <p className="text-gray-500">Loading...</p>}

      {signals && signals.length === 0 && (
        <div className="glass-card p-8 text-center">
          <p className="text-gray-500">No signals generated yet.</p>
          <p className="text-xs text-gray-600 mt-2">
            Signals are generated when the AI model detects high-confidence setups.
          </p>
        </div>
      )}

      <div className="space-y-3">
        {signals?.map((s, i) => (
          <div key={i} className="glass-card p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-3">
                <span className="text-sm font-bold">{s.instrument.tradingsymbol}</span>
                <span
                  className={`px-2 py-0.5 rounded text-xs font-semibold ${
                    s.direction === "BULLISH"
                      ? "bg-neon-green/20 text-neon-green"
                      : s.direction === "BEARISH"
                      ? "bg-neon-red/20 text-neon-red"
                      : "bg-gray-600/20 text-gray-400"
                  }`}
                >
                  {s.direction}
                </span>
                <span className="text-xs text-gray-500">{s.strategy_name}</span>
              </div>
              <span className="text-xs text-gray-500">{new Date(s.ts).toLocaleTimeString()}</span>
            </div>

            <div className="grid grid-cols-6 gap-3 text-xs">
              <div>
                <p className="text-gray-500">Entry</p>
                <p className="font-mono font-semibold">{s.entry}</p>
              </div>
              <div>
                <p className="text-gray-500">SL</p>
                <p className="font-mono text-neon-red">{s.stop_loss}</p>
              </div>
              <div>
                <p className="text-gray-500">T1</p>
                <p className="font-mono text-neon-green">{s.target1}</p>
              </div>
              <div>
                <p className="text-gray-500">Confidence</p>
                <p className="font-semibold text-neon-blue">{(s.confidence * 100).toFixed(1)}%</p>
              </div>
              <div>
                <p className="text-gray-500">RR</p>
                <p className="font-semibold">{s.expected_rr}x</p>
              </div>
              <div>
                <p className="text-gray-500">Regime</p>
                <p>{s.regime}</p>
              </div>
            </div>

            <div className="mt-2 flex flex-wrap gap-1">
              {s.reasons.map((r, j) => (
                <span key={j} className="text-xs px-2 py-0.5 bg-dark-700 rounded text-gray-400">
                  {r}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
