import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** The one card in the system. `spine` paints a coloured edge so a card's status is
 *  legible before any of it is read. */
export function Panel({
  children,
  spine,
  className,
  interactive = false,
}: {
  children: ReactNode;
  spine?: string;
  className?: string;
  interactive?: boolean;
}) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-2xl border bg-card shadow-[0_1px_3px_rgba(18,16,14,0.04)]",
        interactive &&
          "transition-[border-color,box-shadow] hover:border-foreground/15 hover:shadow-[0_2px_10px_rgba(18,16,14,0.06)]",
        className,
      )}
    >
      {spine && (
        <span aria-hidden className={cn("absolute inset-y-0 left-0 w-[3px]", spine)} />
      )}
      {children}
    </div>
  );
}

/** Urgency → spine colour. Kept next to Panel so a new level cannot be added in one
 *  place and forgotten in the other. */
export const SPINE = {
  fundamental: "bg-destructive",
  very_important: "bg-amber-500",
  important: "bg-border",
} as const;
