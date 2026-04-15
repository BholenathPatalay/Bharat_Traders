import { useMemo } from "react";
import type {
  OptionChainRow,
  SelectionSummary,
  SelectionRange,
} from "../types";

export function useSelectionWorker(
  rows: OptionChainRow[],
  range: SelectionRange | null,
): SelectionSummary | null {
  return useMemo(() => {
    if (!range) return null;

    const start = Math.min(range.startIndex, range.endIndex);
    const end = Math.max(range.startIndex, range.endIndex);
    const selectedRows = rows.slice(start, end + 1);
    const isCallSide = range.column === "call";

    let callSum = 0;
    let putSum = 0;
    let callOiSum = 0;
    let putOiSum = 0;
    let callChangeOiSum = 0;
    let putChangeOiSum = 0;

    for (const row of selectedRows) {
      if (isCallSide) {
        callSum += row.call.last_price;
        callOiSum += row.call.open_interest;
        callChangeOiSum += row.call.change_in_oi;
      } else {
        putSum += row.put.last_price;
        putOiSum += row.put.open_interest;
        putChangeOiSum += row.put.change_in_oi;
      }
    }

    return {
      count: selectedRows.length,
      fromStrike: rows[start].strike_price,
      toStrike: rows[end].strike_price,
      column: range.column,
      callSum,
      putSum,
      callOiSum,
      putOiSum,
      callChangeOiSum,
      putChangeOiSum,
    };
  }, [rows, range]);
}
