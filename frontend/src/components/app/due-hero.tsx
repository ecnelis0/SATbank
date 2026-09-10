"use client";

import Link from "next/link";

import { LADDER, INTERVAL_LABELS } from "@/lib/labels";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** The one thing to do now, given the weight it deserves.
 *
 *  Three equal stat tiles made "24 in the bank" and "3 due" look like the same kind
 *  of fact. They are not: one is inventory, the other is the only thing the app is
 *  asking you to do. */
export function DueHero({ due, total }: { due: number; total: number }) {
  const nothingDue = due === 0;

  return (
    <section
      className={cn(
        "rounded-2xl px-7 py-6 shadow-lg",
        nothingDue ? "border bg-card text-card-foreground shadow-sm" : "bg-primary text-primary-foreground",
      )}
    >
      <div className="flex flex-wrap items-center gap-3">
        <p
          className={cn(
            "text-[11px] font-medium uppercase tracking-[0.09em]",
            nothingDue ? "text-muted-foreground" : "text-primary-foreground/70",
          )}
        >
          {nothingDue ? "Nothing due" : "Due right now"}
        </p>
        <div className="ml-auto">
          {nothingDue ? (
            <Link
              href="/log"
              className={cn(buttonVariants({ variant: "secondary", size: "sm" }), "rounded-full")}
            >
              Log a miss
            </Link>
          ) : (
            <Link
              href="/review"
              className="rounded-full bg-primary-foreground px-4 py-1.5 text-[13px] font-medium text-primary transition-opacity hover:opacity-90"
            >
              Start reviewing →
            </Link>
          )}
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-baseline gap-3.5">
        <span className="font-[family-name:var(--font-display)] text-6xl leading-none font-semibold tracking-tight">
          {nothingDue ? total : due}
        </span>
        <p
          className={cn(
            "max-w-xs text-[15px] leading-snug",
            nothingDue ? "text-muted-foreground" : "text-primary-foreground/85",
          )}
        >
          {nothingDue
            ? total === 0
              ? "questions in the bank. Log the first one."
              : "questions in the bank, all waiting on their next rung."
            : `question${due === 1 ? " is" : "s are"} ready to come back to you.`}
        </p>
      </div>

      {/* The ladder, drawn rather than described — it is the product's signature. */}
      <ol className="mt-6 flex gap-1.5" aria-label="The review ladder">
        {LADDER.map((rung, index) => (
          <li key={rung} className="flex-1">
            <div
              className={cn(
                "h-[5px] rounded-full",
                nothingDue
                  ? "bg-muted"
                  : index === 0
                    ? "bg-primary-foreground/95"
                    : index === 1
                      ? "bg-primary-foreground/60"
                      : "bg-primary-foreground/25",
              )}
            />
            <span
              className={cn(
                "mt-2 block font-mono text-[11px]",
                nothingDue ? "text-muted-foreground" : "text-primary-foreground/70",
              )}
            >
              {INTERVAL_LABELS[rung] ?? rung}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
