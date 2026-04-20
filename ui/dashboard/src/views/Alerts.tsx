/**
 * Alerts view — channel availability + timeline of recent notable events.
 *
 * Events are pulled from the existing REST endpoints (orders/trades/risk)
 * and synthesised into a human-readable feed. When the backend later
 * exposes an /api/alerts stream we can swap the derived timeline for the
 * real one without touching the layout.
 */

import { useEffect, useMemo, useState } from "react";
import { api, type OrderRow, type RiskStatus, type TradeRow } from "../api";

type ChannelState = "on" | "off" | "env";
interface Channel {
  name: string;
  blurb: string;
  state: ChannelState;
  requires?: string;
}

function deriveChannels(): Channel[] {
  return [
    {
      name: "Console",
      blurb: "Always-on — streams to uvicorn stdout and the backend log file.",
      state: "on",
    },
    {
      name: "Telegram",
      blurb: "Sends order / risk / signal events to a chat when configured.",
      state: "env",
      requires: "TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID",
    },
    {
      name: "Email (SMTP)",
      blurb: "Transactional alert email on critical events.",
      state: "env",
      requires: "SMTP_HOST / SMTP_USER / SMTP_PASSWORD",
    },
    {
      name: "WhatsApp",
      blurb: "Planned — drop a new AlertChannel subclass when provider is picked.",
      state: "off",
    },
  ];
}

interface AlertItem {
  key: string;
  severity: "info" | "warn" | "err" | "ok" | "pink";
  ts: string;
  title: string;
  sub: string;
}

export default function Alerts() {
  const [orders, setOrders] = useState<OrderRow[]>([]);
  const [trades, setTrades] = useState<TradeRow[]>([]);
  const [risk, setRisk] = useState<RiskStatus | null>(null);

  useEffect(() => {
    async function refresh() {
      try {
        const [o, t, r] = await Promise.all([
          api.orders(25),
          api.trades(25),
          api.risk(),
        ]);
        setOrders(o);
        setTrades(t);
        setRisk(r);
      } catch {
        /* backend down */
      }
    }
    refresh();
    const id = setInterval(refresh, 4000);
    return () => clearInterval(id);
  }, []);

  const channels = useMemo(deriveChannels, []);

  const items = useMemo<AlertItem[]>(() => {
    const xs: AlertItem[] = [];
    if (risk?.kill_switch) {
      xs.push({
        key: "kill-on",
        severity: "err",
        ts: new Date().toISOString(),
        title: "Kill switch is ENGAGED",
        sub: "All new orders are refused until released.",
      });
    }
    if (risk && -risk.realised_pnl_today >= 0.8 * risk.daily_loss_budget) {
      xs.push({
        key: "drawdown-warn",
        severity: "warn",
        ts: new Date().toISOString(),
        title: "Daily drawdown ≥ 80% of budget",
        sub: "Sizing tightens automatically. Review before placing new entries.",
      });
    }
    for (const o of orders.slice(0, 12)) {
      const s = o.status.toUpperCase();
      const sev: AlertItem["severity"] =
        s === "REJECTED" || s === "FAILED"
          ? "err"
          : s === "COMPLETE" || s === "FILLED"
            ? "ok"
            : "info";
      xs.push({
        key: `order-${o.id}`,
        severity: sev,
        ts: o.ts,
        title: `${o.side} ${o.symbol} ×${o.qty} — ${o.status}`,
        sub: `${o.order_type} · ${o.broker}${o.tag ? ` · ${o.tag}` : ""}`,
      });
    }
    for (const t of trades.slice(0, 12)) {
      xs.push({
        key: `trade-${t.id}`,
        severity: t.pnl >= 0 ? "ok" : "warn",
        ts: t.ts,
        title: `${t.side} ${t.symbol} filled @ ${t.price.toFixed(2)}`,
        sub: `P&L ${t.pnl >= 0 ? "+" : ""}${t.pnl.toFixed(2)}`,
      });
    }
    xs.sort((a, b) => (a.ts < b.ts ? 1 : -1));
    return xs.slice(0, 30);
  }, [orders, trades, risk]);

  return (
    <div className="grid">
      <div className="card hero glow">
        <div className="eyebrow">NIFTY 50 · ALERTS</div>
        <h1>Channels &amp; event timeline</h1>
        <div className="muted small" style={{ maxWidth: 720, marginTop: 6 }}>
          Alerts fan out through pluggable channels. The event feed below is
          derived from recent orders, trades, and risk state — swap in the
          server-sent stream when the backend exposes it.
        </div>
      </div>

      <div className="card half">
        <h3>CHANNELS</h3>
        <div className="col" style={{ gap: 8 }}>
          {channels.map((c) => (
            <div
              key={c.name}
              className="row spread"
              style={{
                padding: "10px 12px",
                border: "1px solid var(--panel-border)",
                borderRadius: 10,
                background: "rgba(10,15,26,0.25)",
              }}
            >
              <div className="col" style={{ gap: 2 }}>
                <div className="row" style={{ gap: 8 }}>
                  <strong>{c.name}</strong>
                  <span
                    className={`chip ${
                      c.state === "on"
                        ? "green"
                        : c.state === "env"
                          ? "amber"
                          : "red"
                    }`}
                  >
                    {c.state === "on"
                      ? "ACTIVE"
                      : c.state === "env"
                        ? "NEEDS ENV"
                        : "OFF"}
                  </span>
                </div>
                <span className="muted tiny">{c.blurb}</span>
                {c.requires && (
                  <code className="tiny muted">requires {c.requires}</code>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card half">
        <h3>WHEN ALERTS FIRE</h3>
        <ul className="muted small" style={{ lineHeight: 1.8 }}>
          <li>
            <span className="chip cyan">SIGNAL</span> high-confidence setup
            detected
          </li>
          <li>
            <span className="chip green">ENTRY</span> before &amp; after trade
            entry
          </li>
          <li>
            <span className="chip red">EXIT</span> stop-loss hit, target hit,
            trailing SL moved
          </li>
          <li>
            <span className="chip amber">GUARD</span> broker rejection or
            risk block
          </li>
          <li>
            <span className="chip pink">KILL</span> daily drawdown or
            kill-switch state change
          </li>
        </ul>
      </div>

      <div className="card" style={{ gridColumn: "span 12" }}>
        <div className="row spread" style={{ marginBottom: 10 }}>
          <h3 style={{ margin: 0 }}>EVENT TIMELINE</h3>
          <span className="muted tiny">auto-refresh · 4s</span>
        </div>
        {items.length === 0 ? (
          <div className="empty-state">
            <div className="glyph">◉</div>
            <div className="title">Feed is quiet</div>
            <div className="hint">
              Place a simulated signal or trigger the kill switch to populate
              this timeline.
            </div>
          </div>
        ) : (
          <div className="timeline">
            {items.map((a) => (
              <div key={a.key} className={`item ${a.severity}`}>
                <div>
                  <span className="ts">
                    {new Date(a.ts).toLocaleTimeString()}
                  </span>
                  <span className="msg">{a.title}</span>
                </div>
                <div className="sub">{a.sub}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="disclaimer">
        FEED IS DERIVED · <strong>NOT A SUBSTITUTE FOR BROKER ALERTS</strong> ·
        Always keep Zerodha push notifications on in parallel.
      </div>
    </div>
  );
}
