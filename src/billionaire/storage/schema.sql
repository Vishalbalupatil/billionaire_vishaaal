-- Billionaire Vishaaal schema. SQLite-compatible; works on Postgres with minor
-- tweaks (use SERIAL/BIGSERIAL and proper TIMESTAMP columns).

CREATE TABLE IF NOT EXISTS instruments (
    instrument_token INTEGER PRIMARY KEY,
    tradingsymbol    TEXT    NOT NULL,
    name             TEXT,
    exchange         TEXT    NOT NULL,
    segment          TEXT    NOT NULL,
    lot_size         INTEGER DEFAULT 1,
    tick_size        REAL    DEFAULT 0.05,
    expiry           TEXT,
    strike           REAL,
    option_type      TEXT
);
CREATE INDEX IF NOT EXISTS idx_instruments_symbol ON instruments(tradingsymbol);

CREATE TABLE IF NOT EXISTS ticks (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument_token INTEGER NOT NULL,
    ltp              REAL    NOT NULL,
    volume           INTEGER DEFAULT 0,
    oi               INTEGER DEFAULT 0,
    bid              REAL    DEFAULT 0,
    ask              REAL    DEFAULT 0,
    ts               TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ticks_token_ts ON ticks(instrument_token, ts);

CREATE TABLE IF NOT EXISTS candles (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument_token INTEGER NOT NULL,
    timeframe        TEXT    NOT NULL,
    open             REAL    NOT NULL,
    high             REAL    NOT NULL,
    low              REAL    NOT NULL,
    close            REAL    NOT NULL,
    volume           INTEGER DEFAULT 0,
    oi               INTEGER DEFAULT 0,
    ts               TEXT    NOT NULL,
    UNIQUE(instrument_token, timeframe, ts)
);
CREATE INDEX IF NOT EXISTS idx_candles_lookup ON candles(instrument_token, timeframe, ts);

CREATE TABLE IF NOT EXISTS signals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy    TEXT    NOT NULL,
    symbol      TEXT    NOT NULL,
    setup       TEXT    NOT NULL,
    direction   TEXT    NOT NULL,
    entry       REAL    NOT NULL,
    stop_loss   REAL    NOT NULL,
    target1     REAL    NOT NULL,
    target2     REAL,
    confidence  REAL    NOT NULL,
    regime      TEXT,
    reasons     TEXT,
    invalidation TEXT,
    qty         INTEGER DEFAULT 0,
    rr          REAL    DEFAULT 0,
    payload     TEXT,
    ts          TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals(ts);

CREATE TABLE IF NOT EXISTS orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     TEXT    UNIQUE NOT NULL,
    symbol       TEXT    NOT NULL,
    side         TEXT    NOT NULL,
    qty          INTEGER NOT NULL,
    order_type   TEXT    NOT NULL,
    product      TEXT    NOT NULL,
    limit_price  REAL,
    trigger_price REAL,
    status       TEXT    NOT NULL,
    filled_qty   INTEGER DEFAULT 0,
    avg_price    REAL    DEFAULT 0,
    broker       TEXT    NOT NULL,
    tag          TEXT,
    message      TEXT,
    ts           TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_ts ON orders(ts);

CREATE TABLE IF NOT EXISTS trades (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id  TEXT    NOT NULL,
    order_id  TEXT    NOT NULL,
    symbol    TEXT    NOT NULL,
    side      TEXT    NOT NULL,
    qty       INTEGER NOT NULL,
    price     REAL    NOT NULL,
    pnl       REAL    DEFAULT 0,
    ts        TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trades_ts ON trades(ts);

CREATE TABLE IF NOT EXISTS audit_log (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    event   TEXT    NOT NULL,
    actor   TEXT,
    payload TEXT,
    ts      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts);
