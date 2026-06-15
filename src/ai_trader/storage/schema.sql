-- AI Trader database schema

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    instrument TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry REAL NOT NULL,
    stop_loss REAL NOT NULL,
    target1 REAL NOT NULL,
    target2 REAL,
    confidence REAL NOT NULL,
    regime TEXT,
    strategy_name TEXT,
    reasons TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT UNIQUE NOT NULL,
    instrument TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    order_type TEXT NOT NULL,
    status TEXT NOT NULL,
    filled_qty INTEGER DEFAULT 0,
    avg_price REAL DEFAULT 0,
    broker TEXT DEFAULT 'paper',
    tag TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT UNIQUE NOT NULL,
    order_id TEXT NOT NULL,
    instrument TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    price REAL NOT NULL,
    pnl REAL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    avg_price REAL NOT NULL,
    ltp REAL DEFAULT 0,
    pnl REAL DEFAULT 0,
    strategy_type TEXT,
    status TEXT DEFAULT 'OPEN',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS daily_pnl (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT UNIQUE NOT NULL,
    realized_pnl REAL DEFAULT 0,
    unrealized_pnl REAL DEFAULT 0,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    max_drawdown REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS strategy_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    strategy_type TEXT NOT NULL,
    legs TEXT NOT NULL,
    net_premium REAL,
    max_profit REAL,
    max_loss REAL,
    entry_spot REAL,
    exit_spot REAL,
    pnl REAL,
    status TEXT DEFAULT 'OPEN',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals(ts);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_trades_instrument ON trades(instrument);
CREATE INDEX IF NOT EXISTS idx_daily_pnl_date ON daily_pnl(date);
