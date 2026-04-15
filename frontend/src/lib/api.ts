/// <reference types="vite/client" />

import type {
  AuthTokenResponse,
  AuthUser,
  OptionChainSnapshot,
  WatchlistPinToggleResponse,
  WatchlistPinsResponse,
} from "../types";

// On Windows, `localhost` often resolves to IPv6 (`::1`). If the backend binds only to IPv4
// (e.g. `127.0.0.1`), WebSocket connections to `ws://localhost:8000` can fail.
// Default to `127.0.0.1` to be reliable across dev environments.
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const WS_BASE_URL =
  import.meta.env.VITE_WS_BASE_URL ??
  API_BASE_URL.replace(/^http/i, (value: string) =>
    value.toLowerCase() === "https" ? "wss" : "ws",
  );

function buildUrl(path: string) {
  return new URL(path, API_BASE_URL).toString();
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(buildUrl(path), {
    credentials: "include",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function getOptionChain(token?: string | null) {
  return request<OptionChainSnapshot>("/api/v1/option-chain", {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
}

export function getGoogleAuthorizationUrl() {
  return request<{ authorization_url: string }>(
    "/api/v1/auth/google/authorize?scopes=openid&scopes=email&scopes=profile",
  );
}

export function exchangeGoogleCallback(search: string) {
  return request<AuthTokenResponse>(`/api/v1/auth/google/callback${search}`);
}

export function getCurrentUser(token: string) {
  return request<AuthUser>("/api/v1/users/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function getWatchlistPins(token: string) {
  return request<WatchlistPinsResponse>("/api/v1/watchlist/pins", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function toggleWatchlistPin(token: string, strikePrice: number) {
  return request<WatchlistPinToggleResponse>(
    `/api/v1/watchlist/pins/${strikePrice}`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    },
  );
}

export function getOptionChainSocketUrl() {
  return new URL("/ws/option-chain", WS_BASE_URL).toString();
}
