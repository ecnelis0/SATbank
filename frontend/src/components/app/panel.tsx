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
      data-slot="panel"
      className={cn(
        "relative overflow-hidden rounded-2xl border bg-card shadow-[0_1px_3px_oklch(0.268_0.028_155_/_0.07)]",
        interactive &&
          "transition-[border-color,box-shadow] hover:border-malachite-deep/30 hover:shadow-[0_2px_12px_oklch(0.485_0.078_147_/_0.12)]",
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
  fundamental: "bg-seal",
  very_important: "bg-ochre",
  important: "bg-malachite/45",
} as const;
