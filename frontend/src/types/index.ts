export type ConnectionStatus = "connecting" | "connected" | "disconnected";

export interface OptionLegMetrics {
  last_price: number;
  open_interest: number;
  change_in_oi: number;
  volume: number;
  implied_volatility: number | null;
}

export interface OptionChainRow {
  strike_price: number;
  call: OptionLegMetrics;
  put: OptionLegMetrics;
  pcr: number | null;
}

export interface UnderlyingQuote {
  symbol: string;
  spot_price: number | null;
  change: number | null;
  change_percent: number | null;
  expiry: string | null;
}

export interface OptionChainSummary {
  total_call_oi: number;
  total_put_oi: number;
  total_call_change_oi: number;
  total_put_change_oi: number;
  put_call_ratio: number | null;
  strongest_call_oi_strike: number | null;
  strongest_put_oi_strike: number | null;
}

export interface OptionChainSnapshot {
  type: "snapshot";
  generated_at: string;
  source: string;
  pinned_strikes: number[];
  underlying: UnderlyingQuote;
  summary: OptionChainSummary;
  rows: OptionChainRow[];
}

export interface OptionChainDelta {
  type: "delta";
  generated_at: string;
  changed_rows: OptionChainRow[];
  removed_strikes: number[];
  underlying: UnderlyingQuote | null;
  summary: OptionChainSummary | null;
}

export interface SelectionRange {
  startIndex: number;
  endIndex: number;
  column: "call" | "put";
}

export interface SelectionSummary {
  count: number;
  fromStrike: number;
  toStrike: number;
  column: "call" | "put"; // which side was selected
  callSum: number; // present only for "call", else 0
  putSum: number; // present only for "put", else 0
  callOiSum: number;
  putOiSum: number;
  callChangeOiSum: number;
  putChangeOiSum: number;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
}

export interface AuthUser {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified?: boolean;
  full_name?: string | null;
}

export interface WatchlistPinsResponse {
  strikes: number[];
}

export interface WatchlistPinToggleResponse {
  strike_price: number;
  pinned: boolean;
  strikes: number[];
}
