"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { toast } from "sonner";

import { AnalysisPanel } from "@/components/app/analysis";
import { Empty } from "@/components/app/empty";
import { MistakeImages } from "@/components/app/images";
import { UrgencyBadge } from "@/components/app/urgency-badge";
import { Unreachable } from "@/components/app/unreachable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {remaining} due · this one is the{" "}
          {INTERVAL_LABELS[review.interval_label] ?? review.interval_label} review
        </p>
        <div className="flex items-center gap-2">
          {mistake.urgency && <UrgencyBadge urgency={mistake.urgency} />}
          <Badge variant="outline">{SECTION_LABELS[mistake.section]}</Badge>
        </div>
      </div>

      <Card>
        <CardContent className="space-y-5">
          <p className="text-base leading-relaxed whitespace-pre-line">
            {mistake.question_text}
          </p>

          {mistake.images.length > 0 && <MistakeImages mistake={mistake} />}

          {mistake.choices && (
            <ol className="space-y-1.5 text-sm">
              {mistake.choices.map((choice, index) => (
                <li key={choice} className="text-muted-foreground">
                  <span className="font-mono">{String.fromCharCode(65 + index)}.</span>{" "}
                  {choice}
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
                className="space-y-5"
              >
                <div className="rounded-lg bg-muted/50 px-4 py-3 text-sm">
                  The answer is{" "}
                  <span className="font-medium">{mistake.correct_answer}</span>. Last time
                  you put <span className="font-medium">{mistake.your_answer}</span>.
                </div>
                <AnalysisPanel mistake={mistake} />
                <div className="flex flex-wrap gap-2">
                  <Button
                    onClick={() =>
                      complete.mutate({ id: review.id, outcome: "correct" })
                    }
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
                    onClick={() => complete.mutate({ id: review.id, outcome: "skipped" })}
                    disabled={complete.isPending}
                  >
                    Skip
                  </Button>
                </div>
              </motion.div>
            ) : (
              <motion.div key="hidden" exit={{ opacity: 0 }}>
                <Button variant="secondary" onClick={() => setRevealed(true)}>
                  Show the answer
                </Button>
              </motion.div>
            )}
          </AnimatePresence>
        </CardContent>
      </Card>
    </div>
  );
}
