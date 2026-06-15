import { useCallback } from "react";
import { api, HealthResponse } from "../api";
import { usePolling } from "../hooks/usePolling";

export default function TopBar() {
  const fetcher = useCallback(() => api.health(), []);
  const { data } = usePolling<HealthResponse>(fetcher, 3000);

  const session = data?.session;
  const mode = data?.mode || "...";
  const modeColor =
    mode === "live" ? "text-neon-red" : mode === "paper" ? "text-neon-yellow" : "text-neon-blue";

  return (
    <header className="h-14 bg-dark-800/50 border-b border-dark-600/30 flex items-center justify-between px-6">
      <div className="flex items-center gap-6">
        <span className={`text-sm font-semibold uppercase ${modeColor}`}>
          {mode} mode
        </span>
        {session?.market_open && (
          <span className="flex items-center gap-1.5 text-xs text-neon-green">
            <span className="w-2 h-2 rounded-full bg-neon-green animate-pulse" />
            Market Open
          </span>
        )}
        {session && !session.market_open && (
          <span className="text-xs text-gray-500">Market Closed</span>
        )}
      </div>
      <div className="flex items-center gap-6 text-xs text-gray-400">
        {session && (
          <>
            <span>IST {session.ist_time}</span>
            <span>{session.day}</span>
            {session.expiry_day && (
              <span className="text-neon-yellow font-semibold">EXPIRY DAY</span>
            )}
            <span>Next expiry: {session.next_expiry}</span>
          </>
        )}
      </div>
    </header>
  );
}
