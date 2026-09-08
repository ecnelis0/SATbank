"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { api, keys } from "@/lib/api";
import type { Mistake } from "@/lib/types";

/** Times a question was still wrong when it came back. Mirrors the backend's
 *  `times_missed_again`: a `wrong` review is a real repeat, a `superseded` rung is
 *  bookkeeping from the restart that miss caused. */
export function timesMissedAgain(mistake: Mistake): number {
  return mistake.reviews.filter((review) => review.outcome === "wrong").length;
}

/** What keeps coming back — the thing volume alone never shows.
 *
 *  Ten questions on a topic logged once each is not a weakness. Three missed again
 *  on review is. */
export function Recurring() {
  const { data } = useQuery({
    queryKey: keys.mistakes(),
    queryFn: () => api.listMistakes(),
  });

  if (!data) return null;

  const repeated = data
    .map((mistake) => ({ mistake, times: timesMissedAgain(mistake) }))
    .filter((entry) => entry.times > 0)
    .sort((a, b) => b.times - a.times);

  if (repeated.length === 0) return null;

  const byTopic = new Map<string, number>();
  for (const { mistake, times } of repeated) {
    if (!mistake.topic) continue;
    byTopic.set(mistake.topic, (byTopic.get(mistake.topic) ?? 0) + times);
  }
  const topics = [...byTopic.entries()].sort((a, b) => b[1] - a[1]).slice(0, 4);

  return (
    <section>
      <h2 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
        What keeps coming back
      </h2>
      <p className="mt-1 text-xs text-muted-foreground">
        Questions you were still getting wrong when they came round again.
      </p>

      {topics.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {topics.map(([topic, times]) => (
            <Link
              key={topic}
              href={`/bank?topic=${encodeURIComponent(topic)}`}
              className="rounded-full border px-3 py-1 text-xs transition-colors hover:bg-muted"
            >
              {topic} · missed again {times}×
            </Link>
          ))}
        </div>
      )}

      <ul className="mt-3 space-y-2">
        {repeated.slice(0, 4).map(({ mistake, times }) => (
          <li key={mistake.id}>
            <Link
              href={`/bank/${mistake.id}`}
              className="flex items-start justify-between gap-3 rounded-lg border px-4 py-3 transition-colors hover:bg-muted/50"
            >
              <span className="line-clamp-2 text-sm">{mistake.question_text}</span>
              <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                {times}× missed again
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
