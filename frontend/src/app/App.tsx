import {
  startTransition,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { LoaderCircle } from "lucide-react";
import { Route, Routes, useNavigate } from "react-router-dom";

import {
  exchangeGoogleCallback,
  getCurrentUser,
  getGoogleAuthorizationUrl,
  getOptionChain,
  getWatchlistPins,
  toggleWatchlistPin,
} from "../lib/api";
import { useOptionChainSocket } from "../hooks/useOptionChainSocket";
import { useDashboardStore } from "../store/useDashboardStore";
import type { SelectionSummary } from "../types";
import { DashboardHeader } from "../components/dashboard-header";
import { MarketOverview } from "../components/market-overview";
import { OptionChainTable } from "../components/option-chain-table";
import { SelectionSummaryBar } from "../components/selection-summary-bar";
import { RangeSelector } from "../components/range-selector";
import { Badge } from "../components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { formatCurrency, formatNumber } from "../lib/format";

function DashboardPage() {
  const snapshot = useDashboardStore((state) => state.snapshot);
  const authToken = useDashboardStore((state) => state.authToken);
  const user = useDashboardStore((state) => state.user);
  const pinnedStrikes = useDashboardStore((state) => state.pinnedStrikes);
  const connectionStatus = useDashboardStore((state) => state.connectionStatus);
  const lastUpdated = useDashboardStore((state) => state.lastUpdated);
  const hydrateAuth = useDashboardStore((state) => state.hydrateAuth);
  const setSnapshot = useDashboardStore((state) => state.setSnapshot);
  const setPinnedStrikes = useDashboardStore((state) => state.setPinnedStrikes);
  const setUser = useDashboardStore((state) => state.setUser);
  const logout = useDashboardStore((state) => state.logout);
  const [selectionSummary, setSelectionSummary] =
    useState<SelectionSummary | null>(null);
  const [loginBusy, setLoginBusy] = useState(false);

  // Range calculator result
  const [rangeResult, setRangeResult] = useState<{
    side: "call" | "put";
    min: number;
    max: number;
    sumLtp: number;
    sumOi: number;
    sumOiChg: number;
  } | null>(null);

  useOptionChainSocket();

  useEffect(() => {
    hydrateAuth();
  }, [hydrateAuth]);

  useEffect(() => {
    let active = true;

    async function bootstrap() {
      try {
        const [optionChain, me, pins] = await Promise.all([
          getOptionChain(authToken),
          authToken
            ? getCurrentUser(authToken).catch(() => null)
            : Promise.resolve(null),
          authToken
            ? getWatchlistPins(authToken).catch(() => ({ strikes: [] }))
            : Promise.resolve({ strikes: [] }),
        ]);

        if (!active) {
          return;
        }

        startTransition(() => {
          setSnapshot(optionChain);
          setUser(me);
          setPinnedStrikes(pins.strikes);
        });
      } catch (error) {
        console.error(error);
      }
    }

    bootstrap();

    return () => {
      active = false;
    };
  }, [authToken, setPinnedStrikes, setSnapshot, setUser]);

  const handleLogin = useCallback(async () => {
    try {
      setLoginBusy(true);
      const { authorization_url } = await getGoogleAuthorizationUrl();
      window.location.href = authorization_url;
    } catch (error) {
      console.error(error);
      setLoginBusy(false);
    }
  }, []);

  const handleLogout = useCallback(() => {
    logout();
  }, [logout]);

  const handleTogglePin = useCallback(
    async (strikePrice: number) => {
      if (!authToken) {
        return;
      }

      try {
        const response = await toggleWatchlistPin(authToken, strikePrice);
        setPinnedStrikes(response.strikes);
      } catch (error) {
        console.error(error);
      }
    },
    [authToken, setPinnedStrikes],
  );

  const handleRangeCompute = (
    side: "call" | "put",
    minStrike: number,
    maxStrike: number,
  ) => {
    const filtered =
      snapshot?.rows.filter(
        (r) => r.strike_price >= minStrike && r.strike_price <= maxStrike,
      ) || [];
    let sumLtp = 0,
      sumOi = 0,
      sumOiChg = 0;
    for (const row of filtered) {
      if (side === "call") {
        sumLtp += row.call.last_price;
        sumOi += row.call.open_interest;
        sumOiChg += row.call.change_in_oi;
      } else {
        sumLtp += row.put.last_price;
        sumOi += row.put.open_interest;
        sumOiChg += row.put.change_in_oi;
      }
    }
    setRangeResult({
      side,
      min: minStrike,
      max: maxStrike,
      sumLtp,
      sumOi,
      sumOiChg,
    });
  };

  const footerSummary = useMemo(
    () =>
      `${snapshot?.rows.length ?? 0} strikes loaded | ${pinnedStrikes.length} pinned`,
    [pinnedStrikes.length, snapshot?.rows.length],
  );

  return (
    <div className="min-h-screen px-4 pb-28 pt-2 md:pt-4 md:px-6">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 md:gap-5">
        <DashboardHeader
          user={user}
          connectionStatus={connectionStatus}
          lastUpdated={lastUpdated}
          onLogin={handleLogin}
          onLogout={handleLogout}
        />

        {loginBusy && !user ? (
          <div className="mx-auto flex items-center gap-2 text-sm text-muted-foreground">
            <LoaderCircle className="h-4 w-4 animate-spin" />
            Redirecting to Google OAuth...
          </div>
        ) : null}

        <MarketOverview snapshot={snapshot} />

        <section className="grid gap-4 xl:grid-cols-[1fr_320px]">
          <OptionChainTable
            rows={snapshot?.rows ?? []}
            pinnedStrikes={pinnedStrikes}
            authenticated={Boolean(authToken)}
            onTogglePin={handleTogglePin}
            onRequireAuth={handleLogin}
            onSelectionSummaryChange={setSelectionSummary}
            spotPrice={snapshot?.underlying.spot_price}
          />

          <div className="space-y-4">
            {/* Range Calculator Card (replaces Session Notes) */}
            <RangeSelector
              rows={snapshot?.rows ?? []}
              onCompute={handleRangeCompute}
            />

            {/* Display range calculation result if available */}
            {rangeResult && (
              <Card className="rounded-[28px] border border-white/10 bg-card/90 shadow-glass backdrop-blur-md">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base font-semibold">
                    {rangeResult.side === "call" ? "Calls" : "Puts"} Range
                    Result
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Strikes:</span>
                      <span className="font-mono">
                        {rangeResult.min} – {rangeResult.max}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">LTP Sum:</span>
                      <span className="font-mono">
                        {formatCurrency(rangeResult.sumLtp)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">OI Sum:</span>
                      <span className="font-mono">
                        {formatNumber(rangeResult.sumOi, 0)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">OI Chg Sum:</span>
                      <span className="font-mono">
                        {formatNumber(rangeResult.sumOiChg, 0)}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Status Card (unchanged) */}
            <div className="rounded-[28px] border border-white/10 bg-card/90 p-5 shadow-glass backdrop-blur-md">
              <h2 className="text-base font-semibold">Status</h2>
              <div className="mt-4 space-y-3 text-sm text-muted-foreground">
                <div className="flex items-center justify-between">
                  <span>Rows in memory</span>
                  <span className="font-mono text-foreground">
                    {snapshot?.rows.length ?? 0}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Connection</span>
                  <span className="font-mono text-foreground">
                    {connectionStatus}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Pinned strikes</span>
                  <span className="font-mono text-foreground">
                    {pinnedStrikes.length}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Expiry</span>
                  <span className="font-mono text-foreground">
                    {snapshot?.underlying.expiry ?? "--"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <div className="text-center text-xs uppercase tracking-[0.2em] text-muted-foreground">
          {footerSummary}
        </div>
      </div>

      <SelectionSummaryBar summary={selectionSummary} />
    </div>
  );
}

function OAuthCallbackPage() {
  const navigate = useNavigate();
  const setAuthToken = useDashboardStore((state) => state.setAuthToken);

  useEffect(() => {
    async function complete() {
      try {
        const tokenResponse = await exchangeGoogleCallback(
          window.location.search,
        );
        setAuthToken(tokenResponse.access_token);
        navigate("/", { replace: true });
      } catch (error) {
        console.error("OAuth exchange failed:", error);
        navigate("/", { replace: true });
      }
    }
    complete();
  }, [navigate, setAuthToken]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="rounded-[28px] border border-white/10 bg-card/90 px-6 py-5 shadow-glass backdrop-blur-md">
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <LoaderCircle className="h-4 w-4 animate-spin" />
          Completing secure Google sign-in...
        </div>
      </div>
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/oauth-callback" element={<OAuthCallbackPage />} />
    </Routes>
  );
}
