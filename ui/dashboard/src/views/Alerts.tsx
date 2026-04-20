export default function Alerts() {
  return (
    <div className="grid">
      <div className="card half">
        <h3>Alert Channels</h3>
        <ul className="muted small" style={{ lineHeight: 1.8 }}>
          <li><strong>Console</strong> — always on, shows in server logs.</li>
          <li><strong>Telegram</strong> — set <code>TELEGRAM_BOT_TOKEN</code> and <code>TELEGRAM_CHAT_ID</code>.</li>
          <li><strong>Email (SMTP)</strong> — set <code>SMTP_*</code> env vars.</li>
          <li><em>WhatsApp</em> — drop a new <code>AlertChannel</code> subclass; the abstraction layer is intentionally thin.</li>
        </ul>
      </div>
      <div className="card half">
        <h3>When Alerts Fire</h3>
        <ul className="muted small" style={{ lineHeight: 1.8 }}>
          <li>High-confidence setup detected</li>
          <li>Before trade entry, after entry</li>
          <li>Stop-loss hit, target hit, trailing SL moved</li>
          <li>Broker rejection / risk block</li>
          <li>Daily drawdown / kill-switch state change</li>
        </ul>
      </div>
    </div>
  );
}
