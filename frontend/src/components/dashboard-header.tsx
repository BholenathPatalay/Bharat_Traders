import { Activity, LogIn, LogOut, Radio } from "lucide-react";

import { formatTimestamp } from "../lib/format";
import type { AuthUser, ConnectionStatus } from "../types";
import { ThemeToggle } from "./theme-toggle";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";

interface DashboardHeaderProps {
  user: AuthUser | null;
  connectionStatus: ConnectionStatus;
  lastUpdated: string | null;
  onLogin: () => void;
  onLogout: () => void;
}

export function DashboardHeader({
  user,
  connectionStatus,
  lastUpdated,
  onLogin,
  onLogout,
}: DashboardHeaderProps) {
  const statusVariant =
    connectionStatus === "connected"
      ? "positive"
      : connectionStatus === "connecting"
        ? "primary"
        : "negative";

  return (
    <header className="glass-panel sticky top-4 z-30 mx-auto flex w-full max-w-7xl flex-col items-center justify-between gap-4 rounded-[28px] px-5 py-4 sm:flex-row">
      <div className="flex flex-col items-center gap-2 text-center sm:items-start sm:text-left">
        <div className="flex items-center gap-2">
          <Badge variant="primary" className="text-[10px] sm:text-xs">Live Dashboard</Badge>
          <Badge variant={statusVariant} className="text-[10px] sm:text-xs">
            <Radio className="mr-1 h-3 w-3" />
            {connectionStatus}
          </Badge>
        </div>
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-900 dark:text-white md:text-2xl">
            Nifty 50 Live Option Chain
          </h1>
          <p className="hidden text-xs text-muted-foreground md:block">
            Redis-cached market snapshots, delta streaming, and worker-fast range analytics.
          </p>
        </div>
      </div>

      <div className="flex w-full items-center justify-center gap-3 sm:w-auto sm:justify-end">
        <div className="hidden items-center gap-2 rounded-full bg-slate-900/5 px-3 py-2 text-xs text-muted-foreground dark:bg-white/10 lg:flex">
          <Activity className="h-3.5 w-3.5" />
          Updated {formatTimestamp(lastUpdated)}
        </div>

        <ThemeToggle />

        {user ? (
          <div className="flex items-center gap-2">
            <div className="hidden text-right text-sm md:block">
              <div className="font-medium text-foreground max-w-[120px] truncate">{user.email}</div>
              <div className="text-xs text-muted-foreground">Watchlist enabled</div>
            </div>
            <Button variant="secondary" size="sm" onClick={onLogout} className="h-9 px-3">
              <LogOut className="h-4 w-4 sm:mr-2" />
              <span className="hidden sm:inline">Logout</span>
            </Button>
          </div>
        ) : (
          <Button size="sm" onClick={onLogin} className="h-9 px-3">
            <LogIn className="h-4 w-4 sm:mr-2" />
            <span className="hidden sm:inline">Login with Google</span>
            <span className="sm:hidden">Login</span>
          </Button>
        )}
      </div>
    </header>
  );
}

