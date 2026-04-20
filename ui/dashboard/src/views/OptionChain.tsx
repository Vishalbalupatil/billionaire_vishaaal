/**
 * Option Chain view — demo snapshot until the backend exposes /api/options.
 *
 * Layout is the real one (strike grid with OI heatmap, ATM highlight, PCR /
 * max-pain / call wall / put wall, Greeks in mono). Values are deterministic
 * synthetic so the visual language holds up even offline. An explicit banner
 * makes it clear this is a scaffold view.
 */

import { useMemo, useState } from "react";

function mulberry32(a: number) {
  return function () {
    let t = (a += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const EXPIRIES = ["25-APR-2024", "30-MAY-2024", "27-JUN-2024"];

function buildChain(spot: number, expiryIdx: number) {
  const rand = mulberry32(1000 + expiryIdx);
  const atm = Math.round(spot / 50) * 50;
  const strikes: number[] = [];
  for (let k = atm - 500; k <= atm + 500; k += 50) strikes.push(k);
  return strikes.map((strike) => {
    const dist = (strike - spot) / spot;
    const baseCallOi = Math.round(400000 * Math.exp(-Math.abs(dist) * 20) * (0.6 + rand()));
    const basePutOi = Math.round(400000 * Math.exp(-Math.abs(dist) * 20) * (0.6 + rand()));
    const callChg = Math.round((rand() - 0.5) * baseCallOi * 0.6);
    const putChg = Math.round((rand() - 0.5) * basePutOi * 0.6);
    const callIv = 12 + rand() * 6 + Math.abs(dist) * 60;
    const putIv = 12 + rand() * 6 + Math.abs(dist) * 60;
    const callLtp = Math.max(0.2, spot - strike + rand() * 25);
    const putLtp = Math.max(0.2, strike - spot + rand() * 25);
    return {
      strike,
      call: {
        ltp: callLtp,
        oi: baseCallOi,
        chg: callChg,
        iv: callIv,
        delta: 0.5 + dist * 3,
      },
      put: {
        ltp: putLtp,
        oi: basePutOi,
        chg: putChg,
        iv: putIv,
        delta: -0.5 + dist * 3,
      },
    };
  });
}

export default function OptionChain() {
  const [expiryIdx, setExpiryIdx] = useState(0);
  const spot = 22_385;
  const rows = useMemo(() => buildChain(spot, expiryIdx), [expiryIdx]);
  const atm = Math.round(spot / 50) * 50;

  const maxCallOi = Math.max(...rows.map((r) => r.call.oi));
  const maxPutOi = Math.max(...rows.map((r) => r.put.oi));
  const callWall = rows.reduce((a, b) => (a.call.oi > b.call.oi ? a : b));
  const putWall = rows.reduce((a, b) => (a.put.oi > b.put.oi ? a : b));
  const pcrOi =
    rows.reduce((a, r) => a + r.put.oi, 0) /
    rows.reduce((a, r) => a + r.call.oi, 0);

  function heatColor(oi: number, max: number, kind: "ce" | "pe") {
    const k = Math.min(1, oi / max);
    const base = kind === "ce" ? "107,255,158" : "255,84,116";
    return `rgba(${base},${0.04 + k * 0.28})`;
  }

  return (
    <div className="grid">
      <div className="card hero glow">
        <div className="eyebrow">NIFTY 50 · OPTION CHAIN</div>
        <h1>Weekly &amp; monthly chain · OI heatmap · walls · PCR</h1>
        <div className="muted small" style={{ maxWidth: 720, marginTop: 6 }}>
          Data shown is a deterministic{" "}
          <span className="chip amber">SCAFFOLD</span> snapshot. When live
          Zerodha option data is wired in, OI, IV, and Greeks will update in
          real time — the layout stays the same.
        </div>

        <div className="kpi-row" style={{ marginTop: 14 }}>
          <div className="stat">
            <div className="label">Spot</div>
            <div className="big">{spot.toLocaleString("en-IN")}</div>
          </div>
          <div className="stat">
            <div className="label">ATM</div>
            <div className="big">{atm.toLocaleString("en-IN")}</div>
          </div>
          <div className="stat">
            <div className="label">PCR (OI)</div>
            <div
              className="big"
              style={{
                color:
                  pcrOi > 1.3
                    ? "var(--neon-green)"
                    : pcrOi < 0.7
                      ? "var(--neon-red)"
                      : "var(--neon-amber)",
              }}
            >
              {pcrOi.toFixed(2)}
            </div>
          </div>
          <div className="stat">
            <div className="label">Max pain</div>
            <div className="big">
              {(Math.round((spot - 30) / 50) * 50).toLocaleString("en-IN")}
            </div>
          </div>
        </div>
      </div>

      <div className="card two-thirds">
        <div
          className="row spread"
          style={{ marginBottom: 10, flexWrap: "wrap", gap: 8 }}
        >
          <h3 style={{ margin: 0 }}>STRIKES · CE ←→ PE</h3>
          <div className="segmented">
            {EXPIRIES.map((e, i) => (
              <button
                key={e}
                className={expiryIdx === i ? "active" : ""}
                onClick={() => setExpiryIdx(i)}
              >
                {e.split("-").slice(0, 2).join("-")}
              </button>
            ))}
          </div>
        </div>

        <table className="glow-rows mono" style={{ fontSize: 12 }}>
          <thead>
            <tr>
              <th style={{ color: "var(--neon-green)", textAlign: "right" }}>
                OI Δ
              </th>
              <th style={{ color: "var(--neon-green)", textAlign: "right" }}>
                OI
              </th>
              <th style={{ color: "var(--neon-green)", textAlign: "right" }}>
                LTP (CE)
              </th>
              <th style={{ textAlign: "center", width: 90 }}>STRIKE</th>
              <th style={{ color: "var(--neon-red)", textAlign: "right" }}>
                LTP (PE)
              </th>
              <th style={{ color: "var(--neon-red)", textAlign: "right" }}>
                OI
              </th>
              <th style={{ color: "var(--neon-red)", textAlign: "right" }}>
                OI Δ
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const isAtm = r.strike === atm;
              return (
                <tr
                  key={r.strike}
                  style={
                    isAtm
                      ? {
                          outline: "1px solid rgba(212,175,55,0.40)",
                          background: "rgba(212,175,55,0.06)",
                        }
                      : undefined
                  }
                >
                  <td
                    className="heat ce"
                    style={{ background: heatColor(Math.abs(r.call.chg), maxCallOi, "ce") }}
                  >
                    {r.call.chg >= 0 ? "+" : ""}
                    {(r.call.chg / 1000).toFixed(0)}k
                  </td>
                  <td
                    className="heat ce"
                    style={{ background: heatColor(r.call.oi, maxCallOi, "ce") }}
                  >
                    {(r.call.oi / 1000).toFixed(0)}k
                  </td>
                  <td style={{ textAlign: "right", color: "var(--neon-green)" }}>
                    {r.call.ltp.toFixed(2)}
                  </td>
                  <td
                    style={{
                      textAlign: "center",
                      color: isAtm ? "var(--neon-cyan)" : "var(--text)",
                      fontFamily: "Orbitron",
                      letterSpacing: "0.06em",
                    }}
                  >
                    {r.strike}
                  </td>
                  <td style={{ textAlign: "right", color: "var(--neon-red)" }}>
                    {r.put.ltp.toFixed(2)}
                  </td>
                  <td
                    className="heat pe"
                    style={{ background: heatColor(r.put.oi, maxPutOi, "pe") }}
                  >
                    {(r.put.oi / 1000).toFixed(0)}k
                  </td>
                  <td
                    className="heat pe"
                    style={{ background: heatColor(Math.abs(r.put.chg), maxPutOi, "pe") }}
                  >
                    {r.put.chg >= 0 ? "+" : ""}
                    {(r.put.chg / 1000).toFixed(0)}k
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="card third">
        <h3>WALLS &amp; READ</h3>
        <Pill
          label="Call wall"
          value={`${callWall.strike} · ${(callWall.call.oi / 1000).toFixed(0)}k OI`}
          chip="red"
        />
        <Pill
          label="Put wall"
          value={`${putWall.strike} · ${(putWall.put.oi / 1000).toFixed(0)}k OI`}
          chip="green"
        />
        <Pill
          label="Bias (heuristic)"
          value={
            pcrOi > 1.3
              ? "SUPPORTIVE"
              : pcrOi < 0.7
                ? "HEAVY"
                : "NEUTRAL"
          }
          chip={pcrOi > 1.3 ? "green" : pcrOi < 0.7 ? "red" : "amber"}
        />

        <h3 style={{ marginTop: 14 }}>ATM GREEKS</h3>
        <div className="kpi-row">
          {rows
            .filter((r) => r.strike === atm)
            .flatMap((r) => [
              <div className="stat" key="ce-iv">
                <div className="label">CE IV</div>
                <div className="big">{r.call.iv.toFixed(1)}</div>
              </div>,
              <div className="stat" key="pe-iv">
                <div className="label">PE IV</div>
                <div className="big">{r.put.iv.toFixed(1)}</div>
              </div>,
              <div className="stat" key="ce-d">
                <div className="label">CE Δ</div>
                <div className="big">{r.call.delta.toFixed(2)}</div>
              </div>,
              <div className="stat" key="pe-d">
                <div className="label">PE Δ</div>
                <div className="big">{r.put.delta.toFixed(2)}</div>
              </div>,
            ])}
        </div>
      </div>

      <div className="disclaimer">
        SCAFFOLD DATA · <strong>NOT A LIVE CHAIN</strong> · Values are
        deterministic synthetic until the Zerodha options feed is wired in.
      </div>
    </div>
  );
}

function Pill({
  label,
  value,
  chip,
}: {
  label: string;
  value: string;
  chip: string;
}) {
  return (
    <div
      className="row spread"
      style={{
        padding: "8px 0",
        borderBottom: "1px dashed rgba(212,175,55,0.10)",
      }}
    >
      <span className="muted small">{label}</span>
      <span className={`chip ${chip}`}>{value}</span>
    </div>
  );
}
