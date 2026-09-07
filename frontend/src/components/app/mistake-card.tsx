"use client";

import { formatDistanceToNowStrict, isPast } from "date-fns";
import Link from "next/link";

import { UrgencyBadge } from "@/components/app/urgency-badge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { ERROR_TYPE_LABELS, SECTION_LABELS } from "@/lib/labels";
import type { Mistake } from "@/lib/types";

function nextDue(mistake: Mistake) {
  const open = mistake.reviews
    .filter((r) => r.completed_at === null)
    .sort((a, b) => a.due_at.localeCompare(b.due_at));
  return open[0] ?? null;
}

export function MistakeCard({ mistake }: { mistake: Mistake }) {
  const next = nextDue(mistake);
  const due = next ? isPast(new Date(next.due_at)) : false;

  return (
    <Card className="transition-colors hover:border-foreground/20">
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          {mistake.urgency && <UrgencyBadge urgency={mistake.urgency} />}
          <Badge variant="outline">{SECTION_LABELS[mistake.section]}</Badge>
          {mistake.error_type ? (
            <Badge variant="secondary">{ERROR_TYPE_LABELS[mistake.error_type]}</Badge>
          ) : (
            <Badge variant="outline">
              {
                {
                  not_requested: "no debrief yet",
                  pending: "analysing…",
                  failed: "no analysis",
                  ready: "no slot",
                }[mistake.analysis_status]
              }
            </Badge>
          )}
          {mistake.topic && (
            <span className="text-xs text-muted-foreground">{mistake.topic}</span>
          )}
          {mistake.concepts.map((concept) => (
            <Badge key={concept.id} variant="outline" className="font-normal">
              {concept.title}
            </Badge>
          ))}
        </div>

        <Link href={`/bank/${mistake.id}`} className="block">
          <p className="line-clamp-3 text-sm leading-relaxed">{mistake.question_text}</p>
        </Link>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span>
            You put <span className="font-medium text-foreground">{mistake.your_answer}</span>
            {" · "}answer was{" "}
            <span className="font-medium text-foreground">{mistake.correct_answer}</span>
          </span>
          {next && (
            <span className={due ? "font-medium text-foreground" : undefined}>
              {due
                ? "review due now"
                : `next review in ${formatDistanceToNowStrict(new Date(next.due_at))}`}
            </span>
          )}
          {!next && <span>ladder finished</span>}
        </div>
      </CardContent>
    </Card>
  );
}
