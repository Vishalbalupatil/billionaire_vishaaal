/**
 * "Ask Nifty AI" side panel. This is a **local heuristic** — we do not ship
 * an LLM here. It answers the half-dozen questions operators actually ask
 * during a session using data already in the runtime (forecast, risk,
 * portfolio). Keeps us honest: any answer it gives is backed by state
 * we can point at.
 */

import { useEffect, useRef, useState } from "react";
import { api, type ForecastResp, type HealthResp, type PortfolioResp, type RiskStatus } from "../api";

type Msg = { from: "user" | "ai"; text: string };

const suggestions = [
  "What's Nifty's projected bias right now?",
  "How much risk budget do I have left today?",
  "Am I in live mode?",
  "Summarise my open positions.",
  "Is the kill switch engaged?",
];

export default function AskAI({
  open,
  onClose,
  health,
  risk,
  portfolio,
}: {
  open: boolean;
  onClose: () => void;
  health: HealthResp | null;
  risk: RiskStatus | null;
  portfolio: PortfolioResp | null;
}) {
  const [msgs, setMsgs] = useState<Msg[]>([
    {
      from: "ai",
      text:
        "I can answer questions about the Nifty 50 forecast, your live risk budget, mode, and open positions. " +
        "I do not forecast beyond the published model and I never give financial advice.",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs.length]);

  async function answer(q: string): Promise<string> {
    const lower = q.toLowerCase();
    if (lower.includes("bias") || lower.includes("forecast") || lower.includes("direction")) {
      try {
        const f: ForecastResp = await api.forecast("NIFTY", "bias", 1);
        return (
          `Nifty bias (heuristic, ${f.source}): ${f.bias} with display-confidence ${(f.confidence * 100).toFixed(0)}%. ` +
          `Drift/step = ${f.drift_per_step.toFixed(5)}, vol/step = ${f.vol_per_step.toFixed(5)}. ` +
          `Remember: ${f.disclaimer}`
        );
      } catch {
        return "Forecast endpoint is unreachable. Is the backend running?";
      }
    }
    if (lower.includes("risk") || lower.includes("budget") || lower.includes("loss")) {
      if (!risk) return "Risk state unavailable.";
      const remaining = risk.daily_loss_budget + Math.min(risk.realised_pnl_today, 0);
      return (
        `Daily loss budget: ₹${risk.daily_loss_budget.toLocaleString("en-IN")}. ` +
        `Realised today: ₹${risk.realised_pnl_today.toLocaleString("en-IN")}. ` +
        `Remaining budget: ~₹${Math.max(0, remaining).toLocaleString("en-IN")}. ` +
        `Trades today: ${risk.trades_today}. Consecutive losses: ${risk.consecutive_losses}.`
      );
    }
    if (lower.includes("mode") || lower.includes("live") || lower.includes("paper")) {
      if (!health) return "Health state unavailable.";
      return (
        `Mode: ${health.mode.toUpperCase()}. Broker: ${health.broker}. ` +
        `Live trading ${health.live_trading_enabled ? "UNLOCKED" : "LOCKED"}. ` +
        `WebSocket ${health.websocket?.connected ? "live" : "offline"} with ${health.websocket?.tokens_subscribed ?? 0} tokens subscribed.`
      );
    }
    if (lower.includes("kill")) {
      if (!risk) return "Risk state unavailable.";
      return risk.kill_switch
        ? "Kill switch is ENGAGED. No new orders will be placed until you release it."
        : "Kill switch is OFF. Normal operation.";
    }
    if (lower.includes("position") || lower.includes("open") || lower.includes("pnl")) {
      if (!portfolio) return "Portfolio state unavailable.";
      return (
        `${portfolio.positions.length} open positions. ` +
        `Unrealised P&L: ₹${portfolio.unrealized_pnl.toFixed(2)}. ` +
        `Net exposure: ₹${portfolio.net_exposure.toFixed(2)}. ` +
        `Long: ${portfolio.count_long}, short: ${portfolio.count_short}.`
      );
    }
    return (
      "I can answer: forecast bias, risk budget, mode, kill-switch state, open positions. " +
      "For anything else, look at the tabs on the left."
    );
  }

  async function send(text: string) {
    if (!text.trim() || busy) return;
    setBusy(true);
    setMsgs((m) => [...m, { from: "user", text }]);
    setInput("");
    const a = await answer(text);
    setMsgs((m) => [...m, { from: "ai", text: a }]);
    setBusy(false);
  }

  return (
    <aside className={`askai ${open ? "open" : ""}`} aria-hidden={!open}>
      <div className="row spread" style={{ marginBottom: 10 }}>
        <h3 style={{ margin: 0 }}>ASK NIFTY AI</h3>
        <button className="btn ghost" onClick={onClose}>Close</button>
      </div>
      <p className="muted tiny" style={{ marginTop: 0 }}>
        Local heuristic assistant grounded on the running backend. Not an LLM.
        Not financial advice.
      </p>
      <div style={{ marginTop: 12 }}>
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.from}`}>
            <div className="label">{m.from === "user" ? "You" : "Nifty AI"}</div>
            {m.text}
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <div style={{ marginTop: 14, marginBottom: 6 }} className="muted tiny">
        Try:
      </div>
      <div>
        {suggestions.map((s) => (
          <div key={s} className="suggestion" onClick={() => send(s)}>
            {s}
          </div>
        ))}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        style={{ marginTop: 12 }}
      >
        <input
          className="input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about Nifty bias, risk, mode…"
          disabled={busy}
        />
      </form>
    </aside>
  );
}
