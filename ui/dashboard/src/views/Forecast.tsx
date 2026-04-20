import { useEffect, useState } from "react";
import { api, type ForecastHorizon, type ForecastResp } from "../api";
import ForecastChart from "../components/ForecastChart";

const HORIZONS: { key: ForecastHorizon; label: string; steps: number; blurb: string }[] = [
  { key: "intraday", label: "Intraday · 30m",     steps: 30, blurb: "Projects 30 one-minute steps ahead." },
  { key: "daily",    label: "Daily · 5 sessions", steps: 5,  blurb: "Projects 5 one-session steps ahead." },
  { key: "bias",     label: "Bias only",          steps: 1,  blurb: "Direction label only, no projected path." },
];

export default function Forecast() {
  const [horizon, setHorizon] = useState<ForecastHorizon>("intraday");
  const [symbol] = useState("NIFTY");
  const [data, setData] = useState<ForecastResp | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const cfg = HORIZONS.find((h) => h.key === horizon)!;
        const r = await api.forecast(symbol, horizon, cfg.steps);
        if (!cancelled) {
          setData(r);
          setErr(null);
        }
      } catch (e) {
        if (!cancelled) setErr(String(e));
      }
    }
    load();
    const t = setInterval(load, 5000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [horizon, symbol]);

  const biasClass =
    data?.bias === "BULLISH" ? "up" : data?.bias === "BEARISH" ? "down" : "flat";
  const biasArrow =
    data?.bias === "BULLISH" ? "↑" : data?.bias === "BEARISH" ? "↓" : "→";
  const activeBlurb = HORIZONS.find((h) => h.key === horizon)?.blurb ?? "";

  return (
    <div className="grid">
      <div className="card hero glow">
        <div className="eyebrow">NIFTY 50 · AI FORECAST</div>
        <h1>{symbol} projected path</h1>
        <div className="row spread" style={{ marginTop: 4, flexWrap: "wrap", gap: 12 }}>
          <div className="muted small" style={{ maxWidth: 560 }}>
            Heuristic log-return random-walk projection with 95% confidence band.{" "}
            <strong style={{ color: "var(--neon-amber)" }}>Not a prediction.</strong>{" "}
            Not financial advice. Band widens with horizon under sqrt-t scaling.
          </div>
          <div className="row tag-row">
            {HORIZONS.map((h) => (
              <button
                key={h.key}
                className={`btn toggle ${horizon === h.key ? "active" : ""}`}
                onClick={() => setHorizon(h.key)}
              >
                {h.label}
              </button>
            ))}
          </div>
        </div>

        <div className="row spread" style={{ marginTop: 18, alignItems: "flex-start" }}>
          <div className="col" style={{ flex: 1, minWidth: 0 }}>
            {data ? (
              <ForecastChart
                points={data.points}
                lastPrice={data.last_price}
                bias={data.bias}
              />
            ) : (
              <div className="chart-wrap" style={{ display: "grid", placeItems: "center" }}>
                <span className="muted tiny">{err ?? "Loading forecast…"}</span>
              </div>
            )}
            <div className="muted tiny" style={{ marginTop: 8 }}>{activeBlurb}</div>
          </div>
          <div
            className="col"
            style={{
              flex: "0 0 220px", marginLeft: 18, paddingLeft: 18,
              borderLeft: "1px dashed rgba(212,175,55,0.18)",
            }}
          >
            <div className="muted tiny">BIAS</div>
            <div className="row" style={{ gap: 10, alignItems: "center" }}>
              <div className={`bias-arrow ${biasClass}`}>{biasArrow}</div>
              <div>
                <div className="value mono" style={{ fontFamily: "Orbitron, sans-serif", fontSize: 16 }}>
                  {data?.bias ?? "—"}
                </div>
                <div className="muted tiny">
                  conf {data ? (data.confidence * 100).toFixed(0) : "—"}%
                </div>
              </div>
            </div>
            <div style={{ marginTop: 14 }}>
              <div className="muted tiny">LAST PRICE</div>
              <div className="mono" style={{ fontSize: 20 }}>{data?.last_price.toFixed(2) ?? "—"}</div>
            </div>
            <div style={{ marginTop: 12 }}>
              <div className="muted tiny">SOURCE</div>
              <div className={`badge ${data?.source === "live" ? "bull" : "neutral"}`} style={{ marginTop: 4 }}>
                {data?.source ?? "—"}
              </div>
            </div>
            <div style={{ marginTop: 12 }}>
              <div className="muted tiny">DRIFT / VOL (per step)</div>
              <div className="mono tiny">
                {data ? `${data.drift_per_step.toFixed(5)} / ${data.vol_per_step.toFixed(5)}` : "—"}
              </div>
            </div>
          </div>
        </div>

        <div className="warn" style={{ marginTop: 18 }}>
          <strong>PROJECTION — NOT A PREDICTION.</strong>{" "}
          {data?.disclaimer ??
            "Heuristic projection from historical closes. NOT financial advice."}
        </div>
      </div>
    </div>
  );
}
