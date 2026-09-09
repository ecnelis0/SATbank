"use client";

import { useState } from "react";

import { SelectField } from "@/components/app/fields";
import { useAnalyzeMistake, useUpdateMistake } from "@/components/app/use-mistake";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { UrgencyBadge } from "@/components/app/urgency-badge";
import { ERROR_TYPE_BLURBS, ERROR_TYPE_LABELS, URGENCY_LABELS } from "@/lib/labels";
import {
  ERROR_TYPES,
  URGENCIES,
  type Difficulty,
  type ErrorType,
  type Mistake,
  type Urgency,
} from "@/lib/types";

const ERROR_TYPE_OPTIONS = ERROR_TYPES.map((value) => ({
  value,
  label: ERROR_TYPE_LABELS[value],
}));

const URGENCY_OPTIONS = URGENCIES.map((value) => ({ value, label: URGENCY_LABELS[value] }));

const DIFFICULTY_OPTIONS: { value: Difficulty; label: string }[] = [
  { value: "easy", label: "Easy" },
  { value: "medium", label: "Medium" },
  { value: "hard", label: "Hard" },
];

function Section({ title, body }: { title: string; body: string }) {
  return (
    <div>
      <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {title}
      </h3>
      <p className="mt-1 text-sm leading-relaxed whitespace-pre-line">{body}</p>
    </div>
  );
}

function AnalysisEditor({ mistake, onDone }: { mistake: Mistake; onDone: () => void }) {
  const [draft, setDraft] = useState({
    error_type: (mistake.error_type ?? "other") as ErrorType,
    difficulty: (mistake.difficulty ?? "medium") as Difficulty,
    urgency: (mistake.urgency ?? "important") as Urgency,
    topic: mistake.topic ?? "",
    why_wrong: mistake.why_wrong ?? "",
    trap: mistake.trap ?? "",
    correct_reasoning: mistake.correct_reasoning ?? "",
    takeaway: mistake.takeaway ?? "",
  });
  const save = useUpdateMistake(mistake.id, onDone);

  const field = <K extends keyof typeof draft>(key: K, value: (typeof draft)[K]) =>
    setDraft((current) => ({ ...current, [key]: value }));

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        save.mutate({
          ...draft,
          topic: draft.topic.trim() || null,
        });
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <SelectField
          label="Why you got it wrong"
          value={draft.error_type}
          options={ERROR_TYPE_OPTIONS}
          onChange={(value) => field("error_type", value)}
        />
        <SelectField
          label="How urgent"
          value={draft.urgency}
          options={URGENCY_OPTIONS}
          onChange={(value) => field("urgency", value)}
        />
        <SelectField
          label="Difficulty"
          value={draft.difficulty}
          options={DIFFICULTY_OPTIONS}
          onChange={(value) => field("difficulty", value)}
        />
      </div>

      <div>
        <Label htmlFor="topic">Topic</Label>
        <Input
          id="topic"
          className="mt-1.5"
          value={draft.topic}
          onChange={(event) => field("topic", event.target.value)}
        />
      </div>

      {(
        [
          ["why_wrong", "What went wrong"],
          ["trap", "The trap"],
          ["correct_reasoning", "How it works"],
          ["takeaway", "Remember"],
        ] as const
      ).map(([key, label]) => (
        <div key={key}>
          <Label htmlFor={key}>{label}</Label>
          <Textarea
            id={key}
            rows={key === "takeaway" ? 2 : 3}
            className="mt-1.5"
            value={draft[key]}
            onChange={(event) => field(key, event.target.value)}
          />
        </div>
      ))}

      <div className="flex gap-2">
        <Button type="submit" disabled={save.isPending}>
          {save.isPending ? "Saving…" : "Save"}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

export function AnalysisPanel({
  mistake,
  editable = false,
}: {
  mistake: Mistake;
  editable?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const analyze = useAnalyzeMistake(mistake.id);

  if (editing) {
    return <AnalysisEditor mistake={mistake} onDone={() => setEditing(false)} />;
  }

  if (mistake.analysis_status === "pending") {
    return (
      <div className="space-y-3" aria-live="polite" aria-busy="true">
        <p className="text-sm text-muted-foreground">Analysing this miss…</p>
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-2/3" />
      </div>
    );
  }

  if (mistake.analysis_status === "not_requested") {
    return (
      <div className="space-y-3">
        <p className="text-sm">
          No debrief yet. You logged this one yourself — ask the AI to work out what
          went wrong, or write it up in your own words.
        </p>
        {editable && (
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => analyze.mutate(false)} disabled={analyze.isPending}>
              {analyze.isPending ? "Debriefing…" : "Ask the AI to debrief this"}
            </Button>
            <Button variant="secondary" onClick={() => setEditing(true)}>
              Write it myself
            </Button>
          </div>
        )}
      </div>
    );
  }

  if (mistake.analysis_status === "failed") {
    return (
      <div className="space-y-3">
        <p className="text-sm">
          The analysis did not come back. The question is still logged and still on the
          review ladder.
        </p>
        {mistake.analysis_error && (
          <p className="font-mono text-xs text-muted-foreground">{mistake.analysis_error}</p>
        )}
        {editable && (
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => analyze.mutate(false)} disabled={analyze.isPending}>
              {analyze.isPending ? "Trying again…" : "Try again"}
            </Button>
            <Button variant="secondary" onClick={() => setEditing(true)}>
              Write it myself
            </Button>
          </div>
        )}
      </div>
    );
  }

  const edited = mistake.analysis_edited_at !== null;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        {mistake.urgency && <UrgencyBadge urgency={mistake.urgency} />}
        {mistake.urgency_is_yours && (
          <span className="text-xs text-muted-foreground">your call</span>
        )}
        {mistake.error_type && (
          <Badge variant="secondary">{ERROR_TYPE_LABELS[mistake.error_type]}</Badge>
        )}
        {mistake.topic && <Badge variant="outline">{mistake.topic}</Badge>}
        {mistake.difficulty && <Badge variant="outline">{mistake.difficulty}</Badge>}
      </div>

      {mistake.error_type && (
        <p className="text-sm text-muted-foreground">
          {ERROR_TYPE_BLURBS[mistake.error_type]}
        </p>
      )}

      {mistake.why_wrong && <Section title="Why you got it wrong" body={mistake.why_wrong} />}
      {mistake.trap && <Section title="The trap" body={mistake.trap} />}
      {mistake.correct_reasoning && (
        <Section title="How it works" body={mistake.correct_reasoning} />
      )}

      {mistake.takeaway && (
        <div className="rounded-lg border-l-2 border-primary bg-muted/50 px-4 py-3">
          <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Remember
          </h3>
          <p className="mt-1 text-sm font-medium">{mistake.takeaway}</p>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <p className="text-xs text-muted-foreground">
          {edited
            ? mistake.analyzed_by === "you"
              ? "Written by you."
              : `Analysis by ${mistake.analyzed_by}, edited by you.`
            : mistake.analyzed_by && `Analysis by ${mistake.analyzed_by}.`}
        </p>
        {editable && (
          <div className="ml-auto flex gap-2">
            <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
              Edit the debrief
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={analyze.isPending}
              onClick={() => {
                // Re-running replaces the text. If they wrote it, say so first.
                if (edited && !window.confirm("Replace what you wrote with a fresh AI debrief?"))
                  return;
                analyze.mutate(edited);
              }}
            >
              {analyze.isPending ? "Asking…" : "Re-run the AI"}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
