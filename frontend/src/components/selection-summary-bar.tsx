import { MousePointerSquareDashed } from "lucide-react";
import { cn } from "../lib/cn";
import { formatCurrency, formatNumber } from "../lib/format";
import type { SelectionSummary } from "../types";

interface SelectionSummaryBarProps {
  summary: SelectionSummary | null;
}

export function SelectionSummaryBar({ summary }: SelectionSummaryBarProps) {
  return (
    <div
      className={cn(
        "fixed bottom-4 left-1/2 z-40 w-[min(600px,calc(100%-2rem))] -translate-x-1/2 rounded-[24px] border border-blue-500/20 bg-slate-950/90 px-5 py-4 text-white shadow-2xl backdrop-blur-xl transition-all duration-200",
        summary
          ? "translate-y-0 opacity-100"
          : "pointer-events-none translate-y-6 opacity-0",
      )}
    >
      {summary && (
        <div className="flex flex-col gap-4">
          {/* Header */}
          <div className="flex items-center gap-3">
            <div className="rounded-full bg-blue-500/15 p-2 text-blue-300">
              <MousePointerSquareDashed className="h-4 w-4" />
            </div>
            <div>
              <div className="text-sm font-medium">
                Selected {summary.column === "call" ? "Calls" : "Puts"}:{" "}
                {summary.fromStrike} – {summary.toStrike}
              </div>
              <div className="text-xs text-slate-300">
                {summary.count} strikes
              </div>
            </div>
          </div>

          {/* Sums for the selected side only */}
          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-blue-300">
              {summary.column === "call" ? "Calls" : "Puts"} Summary
            </h3>
            <div className="grid grid-cols-2 gap-x-6 gap-y-1">
              <span className="text-slate-400 text-sm">LTP Sum</span>
              <span className="font-mono text-base font-semibold text-blue-200 text-right">
                {formatCurrency(
                  summary.column === "call" ? summary.callSum : summary.putSum,
                )}
              </span>
              <span className="text-slate-400 text-sm">OI Sum</span>
              <span className="font-mono text-base font-semibold text-blue-200 text-right">
                {formatNumber(
                  summary.column === "call"
                    ? summary.callOiSum
                    : summary.putOiSum,
                  0,
                )}
              </span>
              <span className="text-slate-400 text-sm">OI Chg Sum</span>
              <span className="font-mono text-base font-semibold text-right">
                {formatNumber(
                  summary.column === "call"
                    ? summary.callChangeOiSum
                    : summary.putChangeOiSum,
                  0,
                )}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
