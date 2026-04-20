import type { HealthResp, RiskStatus } from "../api";
import { api } from "../api";

export default function TopBar({
  health,
  risk,
  onAskAI,
}: {
  health: HealthResp | null;
  risk: RiskStatus | null;
  onAskAI?: () => void;
}) {
  const mode = health?.mode ?? "analysis";
  const wsConnected = health?.websocket?.connected;
  const killed = risk?.kill_switch;

  const killToggle = async () => {
    if (killed) await api.release();
    else await api.kill("dashboard");
  };

  return (
    <>
      <div className="row" style={{ gap: 14 }}>
        <span className={`badge mode-${mode}`}>MODE · {mode.toUpperCase()}</span>
        <span className="status-pill">
          <span className={`dot ${wsConnected ? "green" : "red"}`} />
          ws {wsConnected ? "live" : "offline"}
        </span>
        <span className="status-pill">
          <span className="dot amber" /> {health?.broker ?? "—"}
        </span>
        {risk && (
          <span className="status-pill">
            {risk.within_market_hours ? "market open" : "market closed"}
            {" · "}sq-off {risk.past_square_off ? "reached" : "pending"}
          </span>
        )}
      </div>
      <div className="row">
        {onAskAI && (
          <button className="btn primary" onClick={onAskAI}>
            Ask Nifty AI
          </button>
        )}
        <button className="btn" onClick={() => api.squareOff()}>
          Square-off All
        </button>
        <button className={`btn ${killed ? "primary" : "danger"}`} onClick={killToggle}>
          {killed ? "Release Kill Switch" : "Kill Switch"}
        </button>
      </div>
    </>
  );
}
