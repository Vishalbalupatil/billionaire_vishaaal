export default function OptionChain() {
  return (
    <div className="grid">
      <div className="card" style={{ gridColumn: "span 12" }}>
        <h3>Option Chain Insights</h3>
        <p className="muted small" style={{ lineHeight: 1.6 }}>
          When connected to Zerodha, this panel renders: ATM / call wall / put wall, PCR (OI &amp; volume), max-pain,
          ATM IVs, and a quick-read bias. Implementation lives in{" "}
          <code>billionaire.strategy.options_engine.OptionsEngine</code>.
        </p>
        <ul className="muted small" style={{ lineHeight: 1.8 }}>
          <li>Spot / ATM / Call-Wall / Put-Wall badges</li>
          <li>PCR (OI): bullish if &gt; 1.3, bearish if &lt; 0.7 (combined with spot vs max-pain)</li>
          <li>Max-pain converges on expiry day — watch for the drift</li>
          <li>ATM IV rank (14-day) for vol regime</li>
        </ul>
      </div>
    </div>
  );
}
