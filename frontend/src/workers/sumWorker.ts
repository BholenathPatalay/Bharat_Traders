import type { OptionChainRow, SelectionSummary } from "../types";

interface SumWorkerRequest {
  rows: OptionChainRow[];
  startIndex: number;
  endIndex: number;
  column: "call" | "put";
}

interface SumWorkerResponse {
  summary: SelectionSummary | null;
}

self.onmessage = (event: MessageEvent<SumWorkerRequest>) => {
  const { rows, startIndex, endIndex, column } = event.data;

  if (!rows.length || startIndex < 0 || endIndex < 0 || startIndex > endIndex) {
    postMessage({ summary: null } satisfies SumWorkerResponse);
    return;
  }

  const selectedRows = rows.slice(startIndex, endIndex + 1);
  if (!selectedRows.length) {
    postMessage({ summary: null } satisfies SumWorkerResponse);
    return;
  }

  let callSum = 0;
  let putSum = 0;
  let callOiSum = 0;
  let putOiSum = 0;
  let callChangeOiSum = 0;
  let putChangeOiSum = 0;

  for (const row of selectedRows) {
    callSum += row.call.last_price;
    putSum += row.put.last_price;
    callOiSum += row.call.open_interest;
    putOiSum += row.put.open_interest;
    callChangeOiSum += row.call.change_in_oi;
    putChangeOiSum += row.put.change_in_oi;
  }

  postMessage({
    summary: {
      count: selectedRows.length,
      fromStrike: selectedRows[0].strike_price,
      toStrike: selectedRows[selectedRows.length - 1].strike_price,
      column,
      callSum: column === "call" ? callSum : 0,
      putSum: column === "put" ? putSum : 0,
      callOiSum,
      putOiSum,
      callChangeOiSum,
      putChangeOiSum,
    },
  } satisfies SumWorkerResponse);
};

export {};

