import { useCallback, useEffect, useState } from "react";
import { api, ConfigResponse } from "../api";
import { usePolling } from "../hooks/usePolling";

export default function Settings() {
  const configFetcher = useCallback(() => api.config(), []);
  const { data: config } = usePolling<ConfigResponse>(configFetcher, 10000);
  const [loginUrl, setLoginUrl] = useState<string | null>(null);
  const [requestToken, setRequestToken] = useState("");
  const [sessionMsg, setSessionMsg] = useState("");
  const [connected, setConnected] = useState(false);
  const [brokerName, setBrokerName] = useState("");

  // Check auth status on mount and periodically
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const res = await api.authStatus();
        setConnected(res.connected && res.broker === "zerodha");
        setBrokerName(res.broker);
      } catch {
        // ignore
      }
    };
    checkStatus();
    const interval = setInterval(checkStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  const getLoginUrl = async () => {
    try {
      const res = await api.loginUrl();
      setLoginUrl(res.url);
    } catch (e) {
      setLoginUrl("Error fetching login URL");
    }
  };

  const createSession = async () => {
    try {
      const res = await api.createSession(requestToken);
      setSessionMsg(`Session created! Token: ${res.access_token.slice(0, 10)}...`);
      setConnected(true);
      setRequestToken("");
    } catch (e) {
      setSessionMsg(`Error: ${e instanceof Error ? e.message : "Unknown"}`);
    }
  };

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Settings</h2>

      <div className="glass-card p-6">
        <h3 className="text-sm text-gray-400 mb-4">Current Configuration</h3>
        {config && (
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="flex justify-between p-3 bg-dark-700/50 rounded-lg">
              <span className="text-gray-500">Trading Mode</span>
              <span className="font-semibold uppercase">{config.trading_mode}</span>
            </div>
            <div className="flex justify-between p-3 bg-dark-700/50 rounded-lg">
              <span className="text-gray-500">Capital</span>
              <span className="font-mono">₹{config.max_capital.toLocaleString()}</span>
            </div>
            <div className="flex justify-between p-3 bg-dark-700/50 rounded-lg">
              <span className="text-gray-500">Risk per Trade</span>
              <span>{config.risk_per_trade_pct}%</span>
            </div>
            <div className="flex justify-between p-3 bg-dark-700/50 rounded-lg">
              <span className="text-gray-500">Max Daily Loss</span>
              <span className="text-neon-red">{config.max_daily_loss_pct}%</span>
            </div>
            <div className="flex justify-between p-3 bg-dark-700/50 rounded-lg">
              <span className="text-gray-500">Min Confidence</span>
              <span>{(config.min_signal_confidence * 100).toFixed(0)}%</span>
            </div>
            <div className="flex justify-between p-3 bg-dark-700/50 rounded-lg">
              <span className="text-gray-500">Nifty Lot Size</span>
              <span>{config.default_lot_size}</span>
            </div>
          </div>
        )}
      </div>

      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm text-gray-400">Zerodha Authentication</h3>
          {connected ? (
            <span className="px-3 py-1 bg-neon-green/20 text-neon-green text-xs font-semibold rounded-full">
              Connected
            </span>
          ) : (
            <span className="px-3 py-1 bg-neon-red/20 text-neon-red text-xs font-semibold rounded-full">
              Not Connected
            </span>
          )}
        </div>

        {connected ? (
          <div className="space-y-3">
            <div className="p-4 bg-dark-700/50 rounded-lg">
              <p className="text-sm text-neon-green font-medium">Zerodha session is active</p>
              <p className="text-xs text-gray-500 mt-1">
                Broker: {brokerName} — Live market data and trading enabled.
                Session expires daily at midnight. Reconnect tomorrow if needed.
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <button
                onClick={getLoginUrl}
                className="px-4 py-2 bg-neon-blue/20 text-neon-blue rounded-lg text-sm hover:bg-neon-blue/30 transition-all"
              >
                Get Login URL
              </button>
              {loginUrl && (
                <div className="mt-2 p-3 bg-dark-700/50 rounded-lg">
                  <a href={loginUrl} target="_blank" rel="noopener noreferrer" className="text-neon-blue text-sm break-all hover:underline">
                    {loginUrl}
                  </a>
                </div>
              )}
            </div>

            <div>
              <p className="text-xs text-gray-500 mb-2">After login, paste the request_token from the redirect URL:</p>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={requestToken}
                  onChange={(e) => setRequestToken(e.target.value)}
                  placeholder="request_token"
                  className="flex-1 px-3 py-2 bg-dark-700 border border-dark-600 rounded-lg text-sm focus:border-neon-blue outline-none"
                />
                <button
                  onClick={createSession}
                  disabled={!requestToken}
                  className="px-4 py-2 bg-neon-green/20 text-neon-green rounded-lg text-sm hover:bg-neon-green/30 transition-all disabled:opacity-50"
                >
                  Create Session
                </button>
              </div>
              {sessionMsg && (
                <p className={`text-xs mt-2 ${sessionMsg.startsWith("Error") ? "text-neon-red" : "text-neon-green"}`}>
                  {sessionMsg}
                </p>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="glass-card p-6">
        <h3 className="text-sm text-gray-400 mb-4">About</h3>
        <div className="text-sm text-gray-500 space-y-2">
          <p>AI Trader v1.0.0 — Nifty 50 Options Trading Platform</p>
          <p>Powered by XGBoost ensemble ML + Black-Scholes options analytics</p>
          <p className="text-neon-red font-semibold">
            This is NOT financial advice. No profits are guaranteed. Always paper-trade first.
          </p>
        </div>
      </div>
    </div>
  );
}
