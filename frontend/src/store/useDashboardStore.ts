import { create } from "zustand";

import type {
  AuthUser,
  ConnectionStatus,
  OptionChainDelta,
  OptionChainRow,
  OptionChainSnapshot,
} from "../types";

const TOKEN_KEY = "nifty-dashboard-auth-token";

interface DashboardState {
  snapshot: OptionChainSnapshot | null;
  authToken: string | null;
  user: AuthUser | null;
  pinnedStrikes: number[];
  connectionStatus: ConnectionStatus;
  lastUpdated: string | null;
  hydrateAuth: () => void;
  setSnapshot: (snapshot: OptionChainSnapshot) => void;
  applyDelta: (delta: OptionChainDelta) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  setPinnedStrikes: (strikes: number[]) => void;
  setAuthToken: (token: string | null) => void;
  setUser: (user: AuthUser | null) => void;
  logout: () => void;
}

function mergeRows(
  existing: OptionChainRow[],
  deltaRows: OptionChainRow[],
  removed: number[],
) {
  const next = new Map(existing.map((row) => [row.strike_price, row]));
  deltaRows.forEach((row) => next.set(row.strike_price, row));
  removed.forEach((strike) => next.delete(strike));
  return Array.from(next.values()).sort(
    (left, right) => left.strike_price - right.strike_price,
  );
}

export const useDashboardStore = create<DashboardState>((set) => ({
  snapshot: null,
  authToken: null,
  user: null,
  pinnedStrikes: [],
  connectionStatus: "connecting",
  lastUpdated: null,
  hydrateAuth: () => {
    if (typeof window === "undefined") return;
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) set({ authToken: token });
  },
  setSnapshot: (snapshot) => {
    // Defensive check: ensure snapshot has required fields
    if (!snapshot || !snapshot.rows) {
      console.error("Invalid snapshot received", snapshot);
      return;
    }
    set((state) => ({
      snapshot,
      pinnedStrikes: snapshot.pinned_strikes.length
        ? snapshot.pinned_strikes
        : state.pinnedStrikes,
      lastUpdated: snapshot.generated_at,
    }));
  },
  applyDelta: (delta) =>
    set((state) => {
      if (!state.snapshot) return state;
      return {
        snapshot: {
          ...state.snapshot,
          rows: mergeRows(
            state.snapshot.rows,
            delta.changed_rows,
            delta.removed_strikes,
          ),
          summary: delta.summary ?? state.snapshot.summary,
          underlying: delta.underlying ?? state.snapshot.underlying,
          generated_at: delta.generated_at,
        },
        lastUpdated: delta.generated_at,
      };
    }),
  setConnectionStatus: (connectionStatus) => set({ connectionStatus }),
  setPinnedStrikes: (pinnedStrikes) =>
    set({ pinnedStrikes: [...new Set(pinnedStrikes)].sort((a, b) => a - b) }),
  setAuthToken: (token) => {
    if (typeof window !== "undefined") {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    }
    set({ authToken: token });
  },
  setUser: (user) => set({ user }),
  logout: () => {
    if (typeof window !== "undefined") localStorage.removeItem(TOKEN_KEY);
    set({ authToken: null, user: null, pinnedStrikes: [] });
  },
}));
