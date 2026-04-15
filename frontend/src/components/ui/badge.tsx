import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "../../lib/cn";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em]",
  {
    variants: {
      variant: {
        neutral: "bg-slate-900/5 text-slate-700 dark:bg-white/10 dark:text-slate-200",
        positive: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
        negative: "bg-rose-500/15 text-rose-700 dark:text-rose-300",
        primary: "bg-blue-500/15 text-blue-700 dark:text-blue-300",
      },
    },
    defaultVariants: {
      variant: "neutral",
    },
  },
);

interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge };

