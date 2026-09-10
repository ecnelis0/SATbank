"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { toast } from "sonner";

import { AnalysisPanel } from "@/components/app/analysis";
import { Empty } from "@/components/app/empty";
import { MistakeImages } from "@/components/app/images";
import { Panel, SPINE } from "@/components/app/panel";
import { UrgencyBadge } from "@/components/app/urgency-badge";
import { Unreachable } from "@/components/app/unreachable";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, keys } from "@/lib/api";
import { INTERVAL_LABELS, SECTION_LABELS } from "@/lib/labels";
import type { StudentOutcome } from "@/lib/types";

export function ReviewSession() {
  const queryClient = useQueryClient();
  const [revealed, setRevealed] = useState(false);

  const { data: due, isPending, isError, error } = useQuery({
    queryKey: keys.due(),
    queryFn: api.dueReviews,
  });

  const complete = useMutation({
    mutationFn: ({ id, outcome }: { id: string; outcome: StudentOutcome }) =>
      api.completeReview(id, outcome),
    onSuccess: (result) => {
      setRevealed(false);
      queryClient.invalidateQueries({ queryKey: ["reviews"] });
      queryClient.invalidateQueries({ queryKey: ["mistakes"] });
      queryClient.invalidateQueries({ queryKey: keys.stats() });
      toast[result.ladder_restarted ? "info" : "success"](
        result.ladder_restarted
          ? "Back to the top — you'll see this again in an hour."
          : "Marked. Next rung is set.",
      );
    },
    onError: (error: Error) => toast.error(error.message),
  });

  if (isPending) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  // A failed load must not read as "nothing is due" - that is the one message that
  // would make a student close the app believing they had no reviews.
  if (isError) return <Unreachable error={error as Error} />;

  const current = due?.[0];

  if (!current) {
    return (
      <Empty
        title="Nothing is due."
        body="Every question in the bank is waiting on its next rung. Come back when one comes round, or log a new miss."
        action={{ href: "/log", label: "Log a miss" }}
      />
    );
  }

  const { review, mistake } = current;
  const remaining = due.length;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {/* Progress first: knowing how many are left is what makes a session finishable. */}
      <div className="flex items-center gap-3">
        <div className="h-1 flex-1 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-[width]"
            style={{ width: `${Math.max(6, 100 / Math.max(remaining, 1))}%` }}
          />
        </div>
        <span className="shrink-0 font-mono text-xs text-muted-foreground">
          {remaining} left
        </span>
      </div>

      <Panel
        spine={mistake.urgency ? SPINE[mistake.urgency] : undefined}
        className="px-7 py-7"
      >
        <div className="mb-5 flex flex-wrap items-center gap-2">
          {mistake.urgency && <UrgencyBadge urgency={mistake.urgency} />}
          <span className="text-xs text-muted-foreground">
            {SECTION_LABELS[mistake.section]}
            {mistake.topic && ` · ${mistake.topic}`}
          </span>
          <span className="ml-auto rounded-full bg-muted px-2.5 py-1 font-mono text-[11px] text-muted-foreground">
            {INTERVAL_LABELS[review.interval_label] ?? review.interval_label} review
          </span>
        </div>

        {/* The question is the content; everything else is chrome around it. */}
        <p className="text-lg leading-relaxed whitespace-pre-line">
          {mistake.question_text}
        </p>

        {mistake.images.length > 0 && (
          <div className="mt-5">
            <MistakeImages mistake={mistake} />
          </div>
        )}

        {mistake.choices && (
          <ol className="mt-5 space-y-2">
            {mistake.choices.map((choice, index) => (
              <li
                key={choice}
                className="flex gap-3 rounded-xl border bg-background/60 px-4 py-2.5 text-sm"
              >
                <span className="font-mono text-xs text-muted-foreground">
                  {String.fromCharCode(65 + index)}
                </span>
                <span>{choice}</span>
              </li>
            ))}
          </ol>
        )}

        <AnimatePresence initial={false} mode="popLayout">
          {revealed ? (
            <motion.div
              key="revealed"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mt-6 space-y-6"
            >
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl bg-muted/60 px-4 py-3 text-sm">
                <span>
                  <span className="text-muted-foreground">Answer </span>
                  <span className="font-mono font-medium">{mistake.correct_answer}</span>
                </span>
                <span>
                  <span className="text-muted-foreground">You put </span>
                  <span className="font-mono font-medium text-destructive">
                    {mistake.your_answer}
                  </span>
                </span>
              </div>

              <AnalysisPanel mistake={mistake} />

              <div className="flex flex-wrap gap-2 border-t pt-5">
                <Button
                  onClick={() => complete.mutate({ id: review.id, outcome: "correct" })}
                  disabled={complete.isPending}
                >
                  I got it
                </Button>
                <Button
                  variant="destructive"
                  onClick={() => complete.mutate({ id: review.id, outcome: "wrong" })}
                  disabled={complete.isPending}
                >
                  Missed it again
                </Button>
                <Button
                  variant="ghost"
                  className="ml-auto text-muted-foreground"
                  onClick={() => complete.mutate({ id: review.id, outcome: "skipped" })}
                  disabled={complete.isPending}
                >
                  Skip
                </Button>
              </div>
            </motion.div>
          ) : (
            <motion.div key="hidden" exit={{ opacity: 0 }} className="mt-6">
              <Button variant="secondary" onClick={() => setRevealed(true)}>
                Show the answer
              </Button>
              <p className="mt-2 text-xs text-muted-foreground">
                Answer it in your head first — that is the whole point of the ladder.
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </Panel>
    </div>
  );
}
