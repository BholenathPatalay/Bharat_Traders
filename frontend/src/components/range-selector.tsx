import { useState } from "react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { cn } from "../lib/cn";
import type { OptionChainRow } from "../types";

interface RangeSelectorProps {
  rows: OptionChainRow[];
  onCompute: (
    side: "call" | "put",
    minStrike: number,
    maxStrike: number,
  ) => void;
}

export function RangeSelector({ rows, onCompute }: RangeSelectorProps) {
  const [minStrike, setMinStrike] = useState<string>("");
  const [maxStrike, setMaxStrike] = useState<string>("");
  const [selectedSide, setSelectedSide] = useState<"call" | "put">("call");

  const handleCompute = () => {
    const min = parseFloat(minStrike);
    const max = parseFloat(maxStrike);
    if (isNaN(min) || isNaN(max) || min > max) return;
    onCompute(selectedSide, min, max);
  };

  const availableStrikes = rows
    .map((r) => r.strike_price)
    .sort((a, b) => a - b);
  const minAvailable = availableStrikes[0]?.toString() || "";
  const maxAvailable =
    availableStrikes[availableStrikes.length - 1]?.toString() || "";

  return (
    <Card className="rounded-[28px] border border-white/10 bg-card/90 shadow-glass backdrop-blur-md">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">
          Range Calculator
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Button
            size="sm"
            variant={selectedSide === "call" ? "default" : "secondary"}
            onClick={() => setSelectedSide("call")}
            className="flex-1"
          >
            Calls
          </Button>
          <Button
            size="sm"
            variant={selectedSide === "put" ? "default" : "secondary"}
            onClick={() => setSelectedSide("put")}
            className="flex-1"
          >
            Puts
          </Button>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-xs text-muted-foreground">Min Strike</label>
            <Input
              type="number"
              placeholder={minAvailable}
              value={minStrike}
              onChange={(e) => setMinStrike(e.target.value)}
              className="mt-1"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Max Strike</label>
            <Input
              type="number"
              placeholder={maxAvailable}
              value={maxStrike}
              onChange={(e) => setMaxStrike(e.target.value)}
              className="mt-1"
            />
          </div>
        </div>
        <Button onClick={handleCompute} className="w-full">
          Compute Sum
        </Button>
        <p className="text-xs text-muted-foreground">
          Available: {minAvailable} – {maxAvailable}
        </p>
      </CardContent>
    </Card>
  );
}
