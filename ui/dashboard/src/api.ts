const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export interface HealthResponse {
  status: string;
  mode: string;
  session: {
    ist_time: string;
    market_open: boolean;
    pre_market: boolean;
    expiry_day: boolean;
    minutes_to_close: number;
    next_expiry: string;
    day: string;
  };
}

export interface ConfigResponse {
  trading_mode: string;
  max_capital: number;
  risk_per_trade_pct: number;
  max_daily_loss_pct: number;
  max_open_positions: number;
  min_signal_confidence: number;
  default_lot_size: number;
}

export interface RiskResponse {
  kill_switch: boolean;
  daily_pnl: number;
  can_trade: boolean;
  reason: string;
  should_square_off: boolean;
}

export interface Signal {
  instrument: { tradingsymbol: string; exchange: string };
  direction: string;
  entry: number;
  stop_loss: number;
  target1: number;
  target2: number | null;
  confidence: number;
  regime: string;
  reasons: string[];
  strategy_name: string;
  risk_rupees: number;
  expected_rr: number;
  ts: string;
}

export interface Strategy {
  strategy_type: string;
  legs: {
    strike: number;
    option_type: string;
    side: string;
    lots: number;
    premium: number;
  }[];
  net_premium: number;
  max_profit: number;
  max_loss: number;
  breakeven: number[];
  confidence: number;
  reason: string;
  payoff: { spot: number; pnl: number }[];
}

export const api = {
  health: () => get<HealthResponse>("/health"),
  config: () => get<ConfigResponse>("/config"),
  risk: () => get<RiskResponse>("/risk"),
  signals: () => get<Signal[]>("/signals"),
  latestSignal: () => get<Signal | null>("/signals/latest"),
  strategies: () => get<Strategy[]>("/strategies"),
  positions: () => get<unknown[]>("/positions"),
  optionsPositions: () => get<unknown[]>("/positions/options"),
  orders: () => get<unknown[]>("/orders"),
  margins: () => get<Record<string, unknown>>("/account/margins"),
  loginUrl: () => get<{ url: string }>("/auth/login-url"),
  createSession: (request_token: string) => post<{ access_token: string }>("/auth/session", { request_token }),
  killSwitch: (active: boolean, reason: string) => post<{ kill_switch: boolean }>("/risk/kill-switch", { active, reason }),
  tradeStats: () => get<Record<string, unknown>>("/stats"),
  dailyPnl: (days?: number) => get<unknown[]>(`/stats/daily-pnl?days=${days || 30}`),
  signalHistory: (limit?: number) => get<unknown[]>(`/stats/signals?limit=${limit || 50}`),
};
