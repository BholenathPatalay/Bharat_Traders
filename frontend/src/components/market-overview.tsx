import { ArrowDownRight, ArrowUpRight, CandlestickChart, Layers2, Shield, TrendingUp } from "lucide-react";

import { formatCompactNumber, formatCurrency, formatNumber, formatSignedNumber } from "../lib/format";
import type { OptionChainSnapshot } from "../types";
import { Card, CardContent } from "./ui/card";

interface MarketOverviewProps {
  snapshot: OptionChainSnapshot | null;
}

export function MarketOverview({ snapshot }: MarketOverviewProps) {
  const change = snapshot?.underlying.change ?? 0;
  const isPositive = change >= 0;

  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <Card>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>Underlying</span>
            <CandlestickChart className="h-4 w-4" />
          </div>
          <div className="space-y-1">
            <div className="text-2xl font-semibold tracking-tight">
              {formatCurrency(snapshot?.underlying.spot_price)}
            </div>
            <div className={isPositive ? "number-positive text-sm" : "number-negative text-sm"}>
              {isPositive ? <ArrowUpRight className="mr-1 inline h-4 w-4" /> : <ArrowDownRight className="mr-1 inline h-4 w-4" />}
              {formatSignedNumber(snapshot?.underlying.change)} ({formatSignedNumber(snapshot?.underlying.change_percent)}%)
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>Put/Call Ratio</span>
            <TrendingUp className="h-4 w-4" />
          </div>
          <div className="text-2xl font-semibold tracking-tight">{formatNumber(snapshot?.summary.put_call_ratio, 4)}</div>
          <div className="text-sm text-muted-foreground">
            Support strike {formatNumber(snapshot?.summary.strongest_put_oi_strike, 0)}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>Total Call OI</span>
            <Layers2 className="h-4 w-4" />
          </div>
          <div className="text-2xl font-semibold tracking-tight">
            {formatCompactNumber(snapshot?.summary.total_call_oi)}
          </div>
          <div className="number-negative text-sm">
            OI change {formatSignedNumber(snapshot?.summary.total_call_change_oi, 0)}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>Total Put OI</span>
            <Shield className="h-4 w-4" />
          </div>
          <div className="text-2xl font-semibold tracking-tight">
            {formatCompactNumber(snapshot?.summary.total_put_oi)}
          </div>
          <div className="number-positive text-sm">
            OI change {formatSignedNumber(snapshot?.summary.total_put_change_oi, 0)}
          </div>
        </CardContent>
      </Card>
    </section>
  );
}

