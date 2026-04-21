import { useEffect, useState } from "react";
import { api, type ORBTodayResp } from "../api";

type ForecastMode = "scenario" | "probability";

function fmtINR(n: number | undefined) {
  if (n === undefined || Number.isNaN(n)) return "—";
  const sign = n < 0 ? "-" : "";
  const v = Math.abs(n);
  if (v >= 1e5) return `${sign}₹${(v / 1e5).toFixed(2)}L`;
  if (v >= 1e3) return `${sign}₹${(v / 1e3).toFixed(1)}k`;
  return `${sign}₹${v.toFixed(0)}`;
}

export default function Forecast() {
  const [mode, setMode] = useState<ForecastMode>("scenario");
  const [data, setData] = useState<ORBTodayResp | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancel = false;
    async function load() {
      try {
        const r = await api.orbToday("both");
        if (!cancel) { setData(r); setErr(null); }
      } catch (e) {
        if (!cancel) setErr(String(e));
      }
    }
    load();
    const t = setInterval(load, 10_000);
    return () => { cancel = true; clearInterval(t); };
  }, []);

  const snap = data?.snapshot;
  const sc = data?.scenario;
  const pr = data?.probability;
  const brk = data?.current_break;
  const isLive = snap?.source === "live" || snap?.source === "cache";

  return (
    <div className="grid">
      <div className="card hero glow">
        <div className="eyebrow">NIFTY 50 · ORB FORECAST FOR TODAY</div>
        <h1>Today's opening range and what happens if it breaks</h1>
        <div className="row spread" style={{ marginTop: 4, flexWrap: "wrap", gap: 12 }}>
          <div className="muted small" style={{ maxWidth: 620 }}>
            First 5m candle (09:15–09:20 IST) defines the range. A break above
            ORH triggers a LONG futures + ATM call. A break below ORL triggers
            a SHORT futures + ATM put. Options premia are Black-Scholes (india
            VIX σ). Flip the toggle to see the ML-lite probability model trained
            on the recent backtest.{" "}
            <strong style={{ color: "var(--neon-amber)" }}>Not financial advice.</strong>
          </div>
          <div className="row tag-row">
            <button
              className={`btn toggle ${mode === "scenario" ? "active" : ""}`}
              onClick={() => setMode("scenario")}
            >Deterministic scenarios</button>
            <button
              className={`btn toggle ${mode === "probability" ? "active" : ""}`}
              onClick={() => setMode("probability")}
            >Break direction probability</button>
          </div>
        </div>

        <div className="row spread" style={{ marginTop: 18, alignItems: "flex-start", gap: 24 }}>
          <div className="col" style={{ flex: 1, minWidth: 0 }}>
            {err && !data ? (
              <div className="muted tiny">{err}</div>
            ) : !data ? (
              <div className="muted tiny">Loading…</div>
            ) : !snap?.or_formed ? (
              <div className="muted tiny">
                Waiting for first 5-minute candle to close (09:20 IST)…
              </div>
            ) : mode === "scenario" ? (
              <ScenarioGrid data={data} />
            ) : (
              <ProbabilityPanel data={data} />
            )}
          </div>
          <div
            className="col"
            style={{
              flex: "0 0 240px", paddingLeft: 18,
              borderLeft: "1px dashed rgba(130,200,255,0.15)",
            }}
          >
            <div className="muted tiny">SPOT</div>
            <div className="mono" style={{ fontSize: 22 }}>{snap?.spot?.toFixed(2) ?? "—"}</div>
            <div className="muted tiny" style={{ marginTop: 10 }}>VIX</div>
            <div className="mono" style={{ fontSize: 16 }}>
              {snap?.vix ? snap.vix.toFixed(2) : "—"}
            </div>
            <div className="muted tiny" style={{ marginTop: 10 }}>ORH</div>
            <div className="mono">{snap?.or_high?.toFixed(2) ?? "—"}</div>
            <div className="muted tiny" style={{ marginTop: 6 }}>ORL</div>
            <div className="mono">{snap?.or_low?.toFixed(2) ?? "—"}</div>
            <div className="muted tiny" style={{ marginTop: 6 }}>RANGE</div>
            <div className="mono">
              {snap?.or_high && snap?.or_low ? (snap.or_high - snap.or_low).toFixed(2) : "—"}
            </div>
            <div style={{ marginTop: 12 }}>
              <div className="muted tiny">DATA</div>
              <div className={`badge ${isLive ? "bull" : "neutral"}`} style={{ marginTop: 4 }}>
                {snap?.source ?? "—"}
              </div>
            </div>
            {brk && (
              <div style={{ marginTop: 12 }}>
                <div className="muted tiny">BREAK TRIGGERED</div>
                <div className={`badge ${brk.side === "LONG" ? "bull" : "bear"}`} style={{ marginTop: 4 }}>
                  {brk.side} @ {brk.entry_price.toFixed(2)}
                </div>
                <div className="muted tiny" style={{ marginTop: 4 }}>
                  stop {brk.stop_price.toFixed(2)} · tgt {brk.target_price.toFixed(2)}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {sc && (
        <div className="card">
          <h3>SCENARIO MATH (lot size 75, BS σ from VIX)</h3>
          <div className="row" style={{ gap: 24, flexWrap: "wrap" }}>
            <SideDetail
              title="If ORH breaks → LONG" side="LONG" scenario={sc.long_scenario}
              strike={sc.atm_strike} sign={+1}
            />
            <SideDetail
              title="If ORL breaks → SHORT" side="SHORT" scenario={sc.short_scenario}
              strike={sc.atm_strike} sign={-1}
            />
          </div>
          <p className="muted tiny" style={{ marginTop: 10 }}>
            Futures P&L assumes the trade runs to target at 1:{sc.rr} RR. Options
            P&L is BS premium delta, same spot move, with today's VIX-derived σ
            and current-month expiry. Real fills drift ±5–15% from theoretical
            premia for liquid ATM Nifty options.
          </p>
        </div>
      )}

      {pr && (
        <div className="card">
          <h3>PROBABILITY MODEL (multinomial logistic, 5 features)</h3>
          <div className="muted small" style={{ marginBottom: 8 }}>
            Trained on <span className="mono">{pr.n_samples}</span> past ORB
            trades. Features: opening-range %, gap %, VIX, previous-day return,
            day-of-week. Honestly small — treat as a prior, not a prediction.
            Status:{" "}
            <span className={`badge ${pr.model_trained ? "bull" : "neutral"}`}>
              {pr.reason}
            </span>
          </div>
          <ProbBars probs={pr.probs} />
        </div>
      )}
    </div>
  );
}

function SideDetail({
  title, side, scenario, strike, sign,
}: {
  title: string;
  side: "LONG" | "SHORT";
  scenario: NonNullable<ORBTodayResp["scenario"]>["long_scenario"];
  strike: number;
  sign: number;
}) {
  const combined = scenario.futures_pnl_rupees + scenario.option_pnl_rupees;
  const combinedTone = combined >= 0 ? "pos" : "neg";
  return (
    <div style={{ flex: "1 1 260px", minWidth: 260 }}>
      <div className="row" style={{ gap: 8, alignItems: "center", marginBottom: 6 }}>
        <span className={`badge ${side === "LONG" ? "bull" : "bear"}`}>{side}</span>
        <strong className="mono">{title}</strong>
      </div>
      <Row label="Entry (level)" value={scenario.entry.toFixed(2)} />
      <Row label="Stop" value={scenario.stop.toFixed(2)} />
      <Row label="Target" value={scenario.target.toFixed(2)} />
      <Row
        label="Futures P&L @ target"
        value={fmtINR(scenario.futures_pnl_rupees)}
        tone={scenario.futures_pnl_rupees >= 0 ? "pos" : "neg"}
      />
      <Row
        label={`ATM ${side === "LONG" ? "CE" : "PE"} strike`}
        value={String(strike)}
      />
      <Row
        label="Option premium now"
        value={`₹${scenario.option_entry_premium.toFixed(2)}`}
      />
      <Row
        label="Option premium @ target"
        value={`₹${scenario.option_target_premium.toFixed(2)}`}
      />
      <Row
        label="Option P&L @ target"
        value={fmtINR(scenario.option_pnl_rupees)}
        tone={scenario.option_pnl_rupees >= 0 ? "pos" : "neg"}
      />
      <div
        className="row spread"
        style={{
          padding: "6px 0", marginTop: 4,
          borderTop: "1px dashed rgba(130,200,255,0.2)",
        }}
      >
        <strong className="small">Combined target P&L</strong>
        <strong
          className="mono"
          style={{
            color: combinedTone === "pos" ? "var(--neon-green)" : "var(--neon-red)",
          }}
        >
          {fmtINR(combined)}
        </strong>
      </div>
      <div className="muted tiny">
        Direction sign: {sign > 0 ? "+" : ""}{sign}
      </div>
    </div>
  );
}

function ScenarioGrid({ data }: { data: ORBTodayResp }) {
  if (!data.scenario) return null;
  const s = data.scenario;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 16 }}>
      <MetricBox label="ATM strike" value={String(s.atm_strike)} />
      <MetricBox label="Call premium now" value={`₹${s.call_now_premium.toFixed(2)}`} />
      <MetricBox label="Put premium now" value={`₹${s.put_now_premium.toFixed(2)}`} />
      <MetricBox label="RR" value={`1 : ${s.rr}`} />
      <MetricBox
        label="Long target (ORH + 2R)"
        value={s.long_scenario.target.toFixed(2)}
        tone="pos"
      />
      <MetricBox
        label="Short target (ORL - 2R)"
        value={s.short_scenario.target.toFixed(2)}
        tone="neg"
      />
    </div>
  );
}

function ProbabilityPanel({ data }: { data: ORBTodayResp }) {
  if (!data.probability) return <div className="muted tiny">Model not loaded.</div>;
  return (
    <div>
      <ProbBars probs={data.probability.probs} />
      <p className="muted tiny" style={{ marginTop: 10 }}>
        Probabilities sum to 1. The model is trained on past ORB outcomes and
        estimates the likelihood that today's range breaks up (LONG), down
        (SHORT), or not at all (NONE). Not a prediction.
      </p>
    </div>
  );
}

function ProbBars({ probs }: { probs: Record<string, number> }) {
  // Canonical order: LONG, SHORT, NONE.
  const order = ["LONG", "SHORT", "NONE"];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {order.map((k) => {
        const v = Number(probs[k] ?? 0);
        const pct = (v * 100).toFixed(1);
        const color =
          k === "LONG" ? "var(--neon-green, #3af58a)" :
          k === "SHORT" ? "var(--neon-red, #ff5f6d)" : "#8aa";
        return (
          <div key={k}>
            <div className="row spread" style={{ fontSize: 12, marginBottom: 4 }}>
              <span className="mono">{k}</span>
              <span className="mono">{pct}%</span>
            </div>
            <div
              style={{
                width: "100%", height: 10, background: "rgba(130,180,255,0.08)",
                borderRadius: 5, overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${Math.max(2, v * 100)}%`, height: "100%",
                  background: color, boxShadow: `0 0 10px ${color}`,
                  transition: "width 400ms ease",
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Row({ label, value, tone }: { label: string; value: string; tone?: "pos" | "neg" }) {
  return (
    <div className="row spread" style={{ padding: "3px 0" }}>
      <span className="muted tiny">{label}</span>
      <span
        className="mono tiny"
        style={{
          color:
            tone === "pos" ? "var(--neon-green)" :
            tone === "neg" ? "var(--neon-red)"   : "var(--text)",
        }}
      >
        {value}
      </span>
    </div>
  );
}

function MetricBox({
  label, value, tone,
}: { label: string; value: string; tone?: "pos" | "neg" }) {
  return (
    <div
      style={{
        padding: 12,
        border: "1px solid rgba(120,180,255,0.15)",
        borderRadius: 10,
        background: "rgba(15,22,40,0.35)",
      }}
    >
      <div className="muted tiny">{label}</div>
      <div
        className={`mono ${tone ?? ""}`}
        style={{
          fontSize: 18,
          color:
            tone === "pos" ? "var(--neon-green)" :
            tone === "neg" ? "var(--neon-red)"   : "var(--text)",
        }}
      >
        {value}
      </div>
    </div>
  );
}
