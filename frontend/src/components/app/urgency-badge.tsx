import { URGENCY_LABELS, URGENCY_STYLES } from "@/lib/labels";
import type { Urgency } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Not the shadcn Badge: this one carries its own per-urgency colour so the three
 *  levels read as a scale rather than three identical chips. */
export function UrgencyBadge({
  urgency,
  className,
}: {
  urgency: Urgency;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
        URGENCY_STYLES[urgency],
        className,
      )}
    >
      {URGENCY_LABELS[urgency]}
    </span>
  );
}
