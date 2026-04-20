export default function Backtest() {
  return (
    <div className="grid">
      <div className="card" style={{ gridColumn: "span 12" }}>
        <h3>Backtest</h3>
        <p className="muted small">
          Run <code>make backtest</code> or <code>billionaire backtest --symbol NIFTY --bars 1500</code> to run a
          bar-by-bar backtest on synthetic data using all example strategies. Report is written to{" "}
          <code>data/sample_backtest_report.json</code>.
        </p>
        <ul className="muted small" style={{ lineHeight: 1.8 }}>
          <li>Reuses the live SignalEngine + PaperBroker — what backtests sees is what the live bot sees.</li>
          <li>Per-trade P&amp;L, equity curve, win-rate, expectancy, profit factor, max drawdown, Sharpe-like summary.</li>
          <li>Per-strategy breakdown for setup-wise performance.</li>
        </ul>
      </div>
    </div>
  );
}
