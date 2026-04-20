import { useEffect, useState } from "react";
import { api, type UniverseResp } from "../api";

export default function Watchlist() {
  const [uni, setUni] = useState<UniverseResp | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        const r = await api.universe();
        if (!cancel) setUni(r);
      } catch (e) {
        if (!cancel) setErr(String(e));
      }
    })();
    return () => {
      cancel = true;
    };
  }, []);

  const rows = [
    { sym: "NIFTY 50", kind: "index" },
    { sym: "NIFTYFUT", kind: "futures (nearest expiry)" },
    { sym: "NIFTYOPT", kind: "options (auto-loaded)" },
    ...(uni?.equities ?? []).map((s) => ({ sym: s, kind: "nifty 50 constituent" })),
  ];

  return (
    <div className="grid">
      <div className="card" style={{ gridColumn: "span 12" }}>
        <div className="row spread" style={{ marginBottom: 8 }}>
          <h3 style={{ margin: 0 }}>NIFTY 50 WATCHLIST</h3>
          <span className="muted tiny">
            {uni ? `${uni.equities.length} equities · index · futures · options` : "loading…"}
          </span>
        </div>
        {err && <div className="warn">Universe endpoint unreachable: {err}</div>}
        <table>
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Segment</th>
              <th>LTP</th>
              <th>Change</th>
              <th>Regime</th>
              <th>Top signal</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.sym}>
                <td className="mono">{r.sym}</td>
                <td className="muted tiny">{r.kind}</td>
                <td className="mono">—</td>
                <td className="mono">—</td>
                <td>
                  <span className="badge neutral">AWAITING</span>
                </td>
                <td className="muted small">—</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="muted tiny" style={{ marginTop: 10 }}>
          Scope is locked to Nifty 50. Once Kite Connect is authenticated and
          ticks flow, LTP / %-change / regime / top signal populate in real
          time. Nifty futures and options are auto-resolved from the
          instrument master for the current weekly expiry.
        </p>
      </div>
    </div>
  );
}
