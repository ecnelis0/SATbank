"use client";

import { formatDistanceToNowStrict, isPast } from "date-fns";

import { INTERVAL_LABELS, LADDER } from "@/lib/labels";
import type { ReviewEvent } from "@/lib/types";
import { cn } from "@/lib/utils";

/** The five rungs of the current cycle, in order, whatever the API returned. */
function currentCycle(reviews: ReviewEvent[]): ReviewEvent[] {
  if (reviews.length === 0) return [];
  const cycle = Math.max(...reviews.map((r) => r.cycle));
  const inCycle = reviews.filter((r) => r.cycle === cycle);
  return LADDER.map((label) => inCycle.find((r) => r.interval_label === label)).filter(
    (r): r is ReviewEvent => Boolean(r),
  );
}

export function Ladder({ reviews }: { reviews: ReviewEvent[] }) {
  const rungs = currentCycle(reviews);
  const restarts = Math.max(0, ...reviews.map((r) => r.cycle));

  return (
    <div>
      <ol className="flex items-stretch gap-1.5" aria-label="Review schedule">
        {rungs.map((rung) => {
          const answered = rung.completed_at !== null;
          const due = !answered && isPast(new Date(rung.due_at));
          return (
            <li key={rung.id} className="flex-1">
              <div
                className={cn(
                  "h-1.5 rounded-full",
                  answered
                    ? rung.outcome === "wrong"
                      ? "bg-destructive"
                      : "bg-primary"
                    : due
                      ? "bg-primary/40"
                      : "bg-muted",
                )}
              />
              <div
                className={cn(
                  "mt-1.5 text-[11px]",
                  due ? "font-medium text-foreground" : "text-muted-foreground",
                )}
              >
                {INTERVAL_LABELS[rung.interval_label] ?? rung.interval_label}
              </div>
              <div className="text-[11px] text-muted-foreground">
                {answered
                  ? rung.outcome === "wrong"
                    ? "missed"
                    : rung.outcome === "skipped"
                      ? "skipped"
                      : "done"
                  : due
                    ? "due now"
                    : `in ${formatDistanceToNowStrict(new Date(rung.due_at))}`}
              </div>
            </li>
          );
        })}
      </ol>
      {restarts > 0 && (
        <p className="mt-2 text-xs text-muted-foreground">
          Ladder restarted {restarts === 1 ? "once" : `${restarts} times`} — you missed this
          on review, so it comes back from the top.
        </p>
      )}
    </div>
  );
}
