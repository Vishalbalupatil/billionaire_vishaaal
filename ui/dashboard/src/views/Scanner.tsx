import { useCallback } from "react";
import { api, ScanResult, ChartPattern, TrendAnalysis } from "../api";
import { usePolling } from "../hooks/usePolling";

function trendColor(trend: string): string {
  if (trend.includes("STRONG_UP")) return "text-neon-green font-bold";
  if (trend.includes("UP")) return "text-neon-green";
  if (trend.includes("STRONG_DOWN")) return "text-neon-red font-bold";
  if (trend.includes("DOWN")) return "text-neon-red";
  return "text-gray-400";
}

function scoreColor(score: number): string {
  if (score >= 80) return "text-neon-green";
  if (score >= 60) return "text-neon-blue";
  return "text-gray-400";
}

export default function Scanner() {
  const resultsFetcher = useCallback(() => api.scannerResults(), []);
  const patternsFetcher = useCallback(() => api.scannerPatterns(), []);
  const trendsFetcher = useCallback(() => api.scannerTrends(), []);

  const { data: results } = usePolling<ScanResult[]>(resultsFetcher, 5000);
  const { data: patterns } = usePolling<ChartPattern[]>(patternsFetcher, 5000);
  const { data: trends } = usePolling<Record<string, TrendAnalysis>>(trendsFetcher, 5000);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Equity Scanner</h2>

      {/* Scan Results */}
      <div className="glass-card p-6">
        <h3 className="text-sm text-gray-400 mb-4">Top Scan Results</h3>
        {results && results.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-xs border-b border-dark-600">
                  <th className="text-left py-2 px-2">Symbol</th>
                  <th className="text-left py-2 px-2">Type</th>
                  <th className="text-right py-2 px-2">LTP</th>
                  <th className="text-right py-2 px-2">Change</th>
                  <th className="text-right py-2 px-2">Score</th>
                  <th className="text-right py-2 px-2">Entry</th>
                  <th className="text-right py-2 px-2">SL</th>
                  <th className="text-right py-2 px-2">Target</th>
                  <th className="text-right py-2 px-2">RR</th>
                  <th className="text-right py-2 px-2">Vol</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r, i) => (
                  <tr key={i} className="border-b border-dark-700/50 hover:bg-dark-700/30">
                    <td className="py-2 px-2 font-semibold">{r.symbol}</td>
                    <td className="py-2 px-2">
                      <span className="px-2 py-0.5 rounded text-xs bg-dark-600">{r.scan_type}</span>
                    </td>
                    <td className="py-2 px-2 text-right font-mono">{r.ltp.toFixed(2)}</td>
                    <td className={`py-2 px-2 text-right font-mono ${r.change_pct >= 0 ? "text-neon-green" : "text-neon-red"}`}>
                      {r.change_pct >= 0 ? "+" : ""}{r.change_pct.toFixed(1)}%
                    </td>
                    <td className={`py-2 px-2 text-right font-bold ${scoreColor(r.score)}`}>{r.score.toFixed(0)}</td>
                    <td className="py-2 px-2 text-right font-mono">{r.entry.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono text-neon-red">{r.stop_loss.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono text-neon-green">{r.target.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right font-mono">{r.risk_reward.toFixed(1)}x</td>
                    <td className="py-2 px-2 text-right font-mono">{r.volume_ratio.toFixed(1)}x</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-600 text-sm">No scan results yet — waiting for market data</p>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Chart Patterns */}
        <div className="glass-card p-6">
          <h3 className="text-sm text-gray-400 mb-4">Detected Chart Patterns</h3>
          {patterns && patterns.length > 0 ? (
            <div className="space-y-3">
              {patterns.map((p, i) => (
                <div key={i} className="p-3 bg-dark-700/50 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-semibold">{p.symbol}</span>
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      p.bias === "BULLISH" ? "bg-neon-green/20 text-neon-green" : "bg-neon-red/20 text-neon-red"
                    }`}>
                      {p.bias}
                    </span>
                  </div>
                  <p className="text-sm text-gray-300">{p.pattern.replace(/_/g, " ")}</p>
                  <p className="text-xs text-gray-500 mt-1">{p.description}</p>
                  <div className="grid grid-cols-3 gap-2 mt-2 text-xs">
                    <div>
                      <span className="text-gray-500">Entry: </span>
                      <span className="font-mono">{p.entry_zone.toFixed(2)}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">SL: </span>
                      <span className="font-mono text-neon-red">{p.stop_loss.toFixed(2)}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Target: </span>
                      <span className="font-mono text-neon-green">{p.target.toFixed(2)}</span>
                    </div>
                  </div>
                  <div className="mt-1 text-xs text-gray-500">
                    Confidence: <span className="text-neon-blue">{(p.confidence * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-600 text-sm">No patterns detected yet</p>
          )}
        </div>

        {/* Trend Analysis */}
        <div className="glass-card p-6">
          <h3 className="text-sm text-gray-400 mb-4">Trend Analysis</h3>
          {trends && Object.keys(trends).length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs border-b border-dark-600">
                    <th className="text-left py-2">Symbol</th>
                    <th className="text-center py-2">Overall</th>
                    <th className="text-right py-2">Strength</th>
                    <th className="text-right py-2">RSI</th>
                    <th className="text-right py-2">ADX</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(trends).map(([sym, t]) => (
                    <tr key={sym} className="border-b border-dark-700/50">
                      <td className="py-2 font-semibold">{sym}</td>
                      <td className={`py-2 text-center ${trendColor(t.overall)}`}>
                        {t.overall.replace(/_/g, " ")}
                      </td>
                      <td className="py-2 text-right font-mono">{t.strength.toFixed(0)}%</td>
                      <td className={`py-2 text-right font-mono ${
                        t.rsi > 60 ? "text-neon-green" : t.rsi < 40 ? "text-neon-red" : ""
                      }`}>
                        {t.rsi.toFixed(1)}
                      </td>
                      <td className="py-2 text-right font-mono">{t.adx.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-gray-600 text-sm">No trend data yet</p>
          )}
        </div>
      </div>
    </div>
  );
}
