import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { SelectionRange } from "../types";

export function useRangeSelection(maxIndex: number) {
  const [range, setRange] = useState<SelectionRange | null>(null);
  const draggingRef = useRef(false);

  const startSelection = useCallback((index: number, column: SelectionRange["column"]) => {
    draggingRef.current = true;
    setRange({ startIndex: index, endIndex: index, column });
  }, []);

  const updateSelection = useCallback((index: number) => {
    if (!draggingRef.current) {
      return;
    }

    setRange((current) => (current ? { ...current, endIndex: index } : current));
  }, []);

  const finishSelection = useCallback(() => {
    draggingRef.current = false;
  }, []);

  const clearSelection = useCallback(() => {
    draggingRef.current = false;
    setRange(null);
  }, []);

  useEffect(() => {
    const handlePointerUp = () => {
      draggingRef.current = false;
    };

    window.addEventListener("pointerup", handlePointerUp);
    return () => window.removeEventListener("pointerup", handlePointerUp);
  }, []);

  const normalizedRange = useMemo(() => {
    if (!range) {
      return null;
    }

    const startIndex = Math.max(0, Math.min(range.startIndex, range.endIndex));
    const endIndex = Math.min(maxIndex, Math.max(range.startIndex, range.endIndex));
    return { ...range, startIndex, endIndex };
  }, [maxIndex, range]);

  const isIndexSelected = useCallback(
    (index: number) =>
      normalizedRange ? index >= normalizedRange.startIndex && index <= normalizedRange.endIndex : false,
    [normalizedRange],
  );

  return {
    range: normalizedRange,
    startSelection,
    updateSelection,
    finishSelection,
    clearSelection,
    isIndexSelected,
  };
}

