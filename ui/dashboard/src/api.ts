const BASE = "/api";

async function j<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export interface HealthResp {
  status: string;
  mode: "analysis" | "paper" | "live";
  live_trading_enabled: boolean;
  broker: string;
  websocket: { connected: boolean; tokens_subscribed: number; reconnect_attempts?: number };
}

export interface RiskStatus {
  kill_switch: boolean;
  open_positions: number;
  trades_today: number;
  realised_pnl_today: number;
  daily_loss_budget: number;
  consecutive_losses: number;
  within_market_hours: boolean;
  past_square_off: boolean;
  live_trading_enabled: boolean;
  app_mode: string;
}

export interface SignalRow {
  id: number;
  strategy: string;
  symbol: string;
  setup: string;
  direction: string;
  entry: number;
  stop_loss: number;
  target1: number;
  target2?: number;
  confidence: number;
  regime: string;
  qty: number;
  rr: number;
  reasons: string;
  invalidation: string;
  ts: string;
}

export interface OrderRow {
  id: number;
  order_id: string;
  symbol: string;
  side: string;
  qty: number;
  order_type: string;
  product: string;
  status: string;
  avg_price: number;
  broker: string;
  tag: string;
  ts: string;
}

export interface TradeRow {
  id: number;
  trade_id: string;
  order_id: string;
  symbol: string;
  side: string;
  qty: number;
  price: number;
  pnl: number;
  ts: string;
}

export interface PortfolioResp {
  positions: Array<{
    instrument: { tradingsymbol: string };
    quantity: number;
    avg_price: number;
    ltp: number;
    product: string;
  }>;
  unrealized_pnl: number;
  realized_pnl: number;
  gross_exposure: number;
  net_exposure: number;
  count_long: number;
  count_short: number;
}

export type ForecastHorizon = "intraday" | "daily" | "bias";

export interface ForecastPoint {
  step: number;
  ts: string;
  price: number;
  lower: number;
  upper: number;
}

export interface ForecastResp {
  symbol: string;
  horizon: ForecastHorizon;
  source: "live" | "synthetic";
  last_price: number;
  drift_per_step: number;
  vol_per_step: number;
  bias: "BULLISH" | "BEARISH" | "NEUTRAL";
  confidence: number;
  notes: string;
  disclaimer: string;
  points: ForecastPoint[];
}

export interface UniverseResp {
  index: string;
  futures_underlying: string;
  options_underlying: string;
  equities: string[];
}

export const api = {
  health: () => j<HealthResp>(`${BASE}/health`),
  config: () => j<Record<string, unknown>>(`${BASE}/config`),
  risk: () => j<RiskStatus>(`${BASE}/risk`),
  kill: (reason: string) => j(`${BASE}/risk/kill?reason=${encodeURIComponent(reason)}`, { method: "POST" }),
  release: () => j(`${BASE}/risk/release`, { method: "POST" }),
  portfolio: () => j<PortfolioResp>(`${BASE}/portfolio`),
  signals: (limit = 50) => j<SignalRow[]>(`${BASE}/signals?limit=${limit}`),
  orders: (limit = 50) => j<OrderRow[]>(`${BASE}/orders?limit=${limit}`),
  trades: (limit = 50) => j<TradeRow[]>(`${BASE}/trades?limit=${limit}`),
  squareOff: () => j(`${BASE}/square-off`, { method: "POST" }),
  simSignal: (body: Record<string, unknown>) =>
    j(`${BASE}/sim/signal`, { method: "POST", body: JSON.stringify(body) }),
  universe: () => j<UniverseResp>(`${BASE}/universe`),
  forecast: (symbol: string, horizon: ForecastHorizon, steps = 30) =>
    j<ForecastResp>(`${BASE}/forecast?symbol=${encodeURIComponent(symbol)}&horizon=${horizon}&steps=${steps}`),
};
