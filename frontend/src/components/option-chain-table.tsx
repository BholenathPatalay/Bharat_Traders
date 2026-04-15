import { useEffect, useMemo, useRef } from "react";
import { Pin } from "lucide-react";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";

import { cn } from "../lib/cn";
import {
  formatCurrency,
  formatNumber,
  formatSignedNumber,
} from "../lib/format";
import { useDebouncedWindowSize } from "../hooks/useDebouncedWindowSize";
import { useRangeSelection } from "../hooks/useRangeSelection";
import type { OptionChainRow, SelectionSummary } from "../types";
import { useSelectionWorker } from "../workers/useSelectionWorker";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";

interface OptionChainTableProps {
  rows: OptionChainRow[];
  pinnedStrikes: number[];
  authenticated: boolean;
  onTogglePin: (strikePrice: number) => void;
  onRequireAuth: () => void;
  onSelectionSummaryChange: (summary: SelectionSummary | null) => void;
  spotPrice?: number | null; // <-- new: underlying spot price for ATM
}

const columnHelper = createColumnHelper<OptionChainRow>();

export function OptionChainTable({
  rows,
  pinnedStrikes,
  authenticated,
  onTogglePin,
  onRequireAuth,
  onSelectionSummaryChange,
  spotPrice,
}: OptionChainTableProps) {
  const scrollParentRef = useRef<HTMLDivElement | null>(null);
  const { height } = useDebouncedWindowSize();

  // Find ATM strike (closest to spotPrice)
  const atmStrike = useMemo(() => {
    if (!spotPrice || rows.length === 0) return null;
    let closest = rows[0].strike_price;
    let minDiff = Math.abs(spotPrice - closest);
    for (const row of rows) {
      const diff = Math.abs(spotPrice - row.strike_price);
      if (diff < minDiff) {
        minDiff = diff;
        closest = row.strike_price;
      }
    }
    return closest;
  }, [rows, spotPrice]);

  const orderedRows = useMemo(() => {
    const pinned = new Set(pinnedStrikes);
    const topRows = rows.filter((row) => pinned.has(row.strike_price));
    const restRows = rows.filter((row) => !pinned.has(row.strike_price));
    return [...topRows, ...restRows];
  }, [pinnedStrikes, rows]);

  const {
    range,
    startSelection,
    updateSelection,
    finishSelection,
    clearSelection,
    isIndexSelected,
  } = useRangeSelection(Math.max(orderedRows.length - 1, 0));

  const selectionSummary = useSelectionWorker(orderedRows, range);

  useEffect(() => {
    onSelectionSummaryChange(selectionSummary);
  }, [onSelectionSummaryChange, selectionSummary]);

  const columns = useMemo(
    () => [
      columnHelper.display({
        id: "pin",
        header: "",
        cell: ({ row }) => {
          const strikePrice = row.original.strike_price;
          const isPinned = pinnedStrikes.includes(strikePrice);

          return (
            <Button
              size="icon"
              variant="ghost"
              className={cn(
                "h-8 w-8 rounded-full",
                isPinned && "text-blue-500",
              )}
              onClick={() =>
                authenticated ? onTogglePin(strikePrice) : onRequireAuth()
              }
              aria-label={`Pin strike ${strikePrice}`}
            >
              <Pin className={cn("h-4 w-4", isPinned && "fill-current")} />
            </Button>
          );
        },
      }),
      columnHelper.accessor((row) => row.call.open_interest, {
        id: "callOi",
        header: "Call OI",
        cell: (info) => (
          <span className="font-mono">{formatNumber(info.getValue(), 0)}</span>
        ),
      }),
      columnHelper.accessor((row) => row.call.change_in_oi, {
        id: "callOiChange",
        header: "Call OI Chg",
        cell: (info) => (
          <span
            className={cn(
              "font-mono",
              info.getValue() >= 0 ? "number-positive" : "number-negative",
            )}
          >
            {formatSignedNumber(info.getValue(), 0)}
          </span>
        ),
      }),
      columnHelper.accessor((row) => row.call.last_price, {
        id: "callLtp",
        header: "Calls LTP",
        cell: (info) => (
          <span className="font-mono">{formatCurrency(info.getValue())}</span>
        ),
      }),
      columnHelper.accessor((row) => row.strike_price, {
        id: "strike",
        header: "Strike",
        cell: (info) => (
          <span className="font-mono font-semibold">
            {formatNumber(info.getValue(), 0)}
            {info.getValue() === atmStrike && (
              <span className="ml-2 text-xs font-normal text-blue-400">
                ATM
              </span>
            )}
          </span>
        ),
      }),
      columnHelper.accessor((row) => row.put.last_price, {
        id: "putLtp",
        header: "Puts LTP",
        cell: (info) => (
          <span className="font-mono">{formatCurrency(info.getValue())}</span>
        ),
      }),
      columnHelper.accessor((row) => row.put.change_in_oi, {
        id: "putOiChange",
        header: "Put OI Chg",
        cell: (info) => (
          <span
            className={cn(
              "font-mono",
              info.getValue() >= 0 ? "number-positive" : "number-negative",
            )}
          >
            {formatSignedNumber(info.getValue(), 0)}
          </span>
        ),
      }),
      columnHelper.accessor((row) => row.put.open_interest, {
        id: "putOi",
        header: "Put OI",
        cell: (info) => (
          <span className="font-mono">{formatNumber(info.getValue(), 0)}</span>
        ),
      }),
    ],
    [authenticated, onRequireAuth, onTogglePin, pinnedStrikes, atmStrike],
  );

  const table = useReactTable({
    data: orderedRows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const tableRows = table.getRowModel().rows;
  const rowVirtualizer = useVirtualizer({
    count: tableRows.length,
    getScrollElement: () => scrollParentRef.current,
    estimateSize: () => 56,
    overscan: 10,
  });

  useEffect(() => {
    rowVirtualizer.measure();
  }, [height, rowVirtualizer]);

  useEffect(() => {
    if (range && range.endIndex >= orderedRows.length) {
      clearSelection();
    }
  }, [clearSelection, orderedRows.length, range]);

  return (
    <Card className="overflow-hidden">
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <div className="min-w-[900px] xl:min-w-full">
            <div className="subtle-divider grid grid-cols-[56px_120px_110px_110px_120px_110px_110px_120px] xl:grid-cols-[56px_1.1fr_1fr_1fr_120px_1fr_1fr_1.1fr] gap-3 px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              {table.getFlatHeaders().map((header) => {
                const isStrike = header.id === "strike";
                return (
                  <div
                    key={header.id}
                    className={cn(
                      isStrike && "sticky left-[396px] z-20 bg-background/95 text-center backdrop-blur-md md:static md:bg-transparent md:z-auto",
                    )}
                  >
                    {flexRender(header.column.columnDef.header, header.getContext())}
                  </div>
                );
              })}
            </div>

        <div
          ref={scrollParentRef}
          className="hide-scrollbar h-[min(80vh,900px)] overflow-auto"
        >
          {orderedRows.length === 0 ? (
            <div className="flex h-64 items-center justify-center px-6 text-center text-sm text-muted-foreground">
              No option-chain rows were detected from the current INDstocks
              payload. The parser is ready for live data once the provider
              returns option rows.
            </div>
          ) : (
            <div
              className="relative"
              style={{
                height: `${rowVirtualizer.getTotalSize()}px`,
              }}
            >
              {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                const row = tableRows[virtualRow.index];
                const isAtmRow = row.original.strike_price === atmStrike;

                return (
                    <div
                      key={row.id}
                      className={cn(
                        "subtle-divider absolute left-0 top-0 grid w-full grid-cols-[56px_120px_110px_110px_120px_110px_110px_120px] xl:grid-cols-[56px_1.1fr_1fr_1fr_120px_1fr_1fr_1.1fr] gap-3 px-4 py-3 text-sm",
                        isAtmRow && "bg-blue-500/5 border-l-2 border-l-blue-500",
                      )}
                      style={{
                        transform: `translateY(${virtualRow.start}px)`,
                      }}
                    >
                      {row.getVisibleCells().map((cell) => {
                        const isStrike = cell.column.id === "strike";
                        const isCallSide = cell.column.id.startsWith("call");
                        const isPutSide = cell.column.id.startsWith("put");
                        const isSelectable =
                          (isCallSide || isPutSide) &&
                          range?.column === (isCallSide ? "call" : "put");
                        const selected =
                          isSelectable && isIndexSelected(row.index);

                        return (
                          <div
                            key={cell.id}
                            className={cn(
                              "flex min-h-9 items-center rounded-xl px-2 text-sm",
                              isStrike && "sticky left-[396px] z-20 justify-center bg-background/95 backdrop-blur-md md:static md:bg-transparent md:z-auto",
                              isSelectable &&
                                "cursor-cell select-none transition-colors",
                              selected &&
                                "bg-blue-500/20 text-blue-700 dark:text-blue-100",
                            )}
                          onPointerDown={
                            isSelectable
                              ? () =>
                                  startSelection(
                                    row.index,
                                    isCallSide ? "call" : "put",
                                  )
                              : undefined
                          }
                          onPointerEnter={
                            isSelectable
                              ? () => updateSelection(row.index)
                              : undefined
                          }
                          onPointerUp={
                            isSelectable ? finishSelection : undefined
                          }
                        >
                          {flexRender(
                            cell.column.columnDef.cell,
                            cell.getContext(),
                          )}
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  </CardContent>
</Card>
);
}
