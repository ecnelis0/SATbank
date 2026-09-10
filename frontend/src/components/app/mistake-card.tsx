"use client";

import { formatDistanceToNowStrict, isPast } from "date-fns";
import Link from "next/link";

import { Panel, SPINE } from "@/components/app/panel";
import { UrgencyBadge } from "@/components/app/urgency-badge";
import { ERROR_TYPE_LABELS, SECTION_LABELS } from "@/lib/labels";
import type { Mistake } from "@/lib/types";
import { cn } from "@/lib/utils";

function nextDue(mistake: Mistake) {
  const open = mistake.reviews
    .filter((r) => r.completed_at === null)
    .sort((a, b) => a.due_at.localeCompare(b.due_at));
  return open[0] ?? null;
}

export function MistakeCard({ mistake }: { mistake: Mistake }) {
  const next = nextDue(mistake);
  const due = next ? isPast(new Date(next.due_at)) : false;

  const status =
    mistake.analysis_status === "not_requested"
      ? "no debrief yet"
      : mistake.analysis_status === "pending"
        ? "analysing…"
        : mistake.analysis_status === "failed"
          ? "no analysis"
          : null;

  return (
    <Panel
      interactive
      spine={mistake.urgency ? SPINE[mistake.urgency] : undefined}
      className="px-5 py-4"
    >
      <Link href={`/bank/${mistake.id}`} className="block space-y-2.5">
        {/* One line of metadata, quiet, so the question itself is what you read. */}
        <div className="flex flex-wrap items-center gap-2">
          {mistake.urgency && <UrgencyBadge urgency={mistake.urgency} />}
          <span className="text-xs text-muted-foreground">
            {SECTION_LABELS[mistake.section]}
            {mistake.error_type && ` · ${ERROR_TYPE_LABELS[mistake.error_type]}`}
            {mistake.topic && ` · ${mistake.topic}`}
          </span>
          {status && (
            <span className="rounded-full border border-dashed px-2 py-0.5 text-[11px] text-muted-foreground">
              {status}
            </span>
          )}
          {mistake.concepts.map((concept) => (
            <span
              key={concept.id}
              className="rounded-full bg-accent px-2 py-0.5 text-[11px] text-accent-foreground"
            >
              {concept.title}
            </span>
          ))}
        </div>

        <p className="line-clamp-2 leading-snug">{mistake.question_text}</p>

        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-muted-foreground">
          <span>
            you put <span className="font-mono text-destructive">{mistake.your_answer}</span>
            <span className="px-1.5">·</span>answer{" "}
            <span className="font-mono text-foreground">{mistake.correct_answer}</span>
          </span>
          {mistake.tags?.map((tag) => (
            <span key={tag} className="rounded-full bg-muted px-2 py-0.5">
              {tag}
            </span>
          ))}
          <span
            className={cn(
              "ml-auto rounded-full px-2.5 py-0.5",
              due ? "bg-primary font-medium text-primary-foreground" : "bg-muted",
            )}
          >
            {next
              ? due
                ? "due now"
                : `in ${formatDistanceToNowStrict(new Date(next.due_at))}`
              : "ladder finished"}
          </span>
        </div>
      </Link>
    </Panel>
  );
}
