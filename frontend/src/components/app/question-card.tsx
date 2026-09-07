"use client";

import { useState } from "react";

import { SelectField } from "@/components/app/fields";
import { useUpdateMistake } from "@/components/app/use-mistake";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { SECTION_LABELS } from "@/lib/labels";
import type { Mistake, Section } from "@/lib/types";

const SECTION_OPTIONS = (Object.keys(SECTION_LABELS) as Section[]).map((value) => ({
  value,
  label: SECTION_LABELS[value],
}));

function QuestionEditor({ mistake, onDone }: { mistake: Mistake; onDone: () => void }) {
  const [draft, setDraft] = useState({
    section: mistake.section,
    source: mistake.source ?? "",
    question_text: mistake.question_text,
    choices: (mistake.choices ?? []).join("\n"),
    your_answer: mistake.your_answer,
    correct_answer: mistake.correct_answer,
    student_note: mistake.student_note ?? "",
  });
  const save = useUpdateMistake(mistake.id, onDone);

  const field = <K extends keyof typeof draft>(key: K, value: (typeof draft)[K]) =>
    setDraft((current) => ({ ...current, [key]: value }));

  const choices = draft.choices
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        save.mutate({
          section: draft.section,
          source: draft.source.trim() || null,
          question_text: draft.question_text.trim(),
          choices: choices.length > 0 ? choices : null,
          your_answer: draft.your_answer.trim(),
          correct_answer: draft.correct_answer.trim(),
          student_note: draft.student_note.trim() || null,
        });
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <SelectField
          label="Section"
          value={draft.section}
          options={SECTION_OPTIONS}
          onChange={(value) => field("section", value)}
        />
        <div>
          <Label htmlFor="edit-source">Where it came from</Label>
          <Input
            id="edit-source"
            className="mt-1.5"
            value={draft.source}
            onChange={(event) => field("source", event.target.value)}
          />
        </div>
      </div>

      <div>
        <Label htmlFor="edit-question">The question</Label>
        <Textarea
          id="edit-question"
          rows={5}
          className="mt-1.5"
          value={draft.question_text}
          onChange={(event) => field("question_text", event.target.value)}
        />
      </div>

      <div>
        <Label htmlFor="edit-choices">Answer choices</Label>
        <Textarea
          id="edit-choices"
          rows={4}
          className="mt-1.5"
          placeholder="One per line"
          value={draft.choices}
          onChange={(event) => field("choices", event.target.value)}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <Label htmlFor="edit-your-answer">You put</Label>
          <Input
            id="edit-your-answer"
            className="mt-1.5"
            value={draft.your_answer}
            onChange={(event) => field("your_answer", event.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="edit-correct-answer">The answer was</Label>
          <Input
            id="edit-correct-answer"
            className="mt-1.5"
            value={draft.correct_answer}
            onChange={(event) => field("correct_answer", event.target.value)}
          />
        </div>
      </div>

      <div>
        <Label htmlFor="edit-note">What happened?</Label>
        <Textarea
          id="edit-note"
          rows={3}
          className="mt-1.5"
          value={draft.student_note}
          onChange={(event) => field("student_note", event.target.value)}
        />
      </div>

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

export function QuestionCard({ mistake }: { mistake: Mistake }) {
  const [editing, setEditing] = useState(false);

  if (editing) {
    return <QuestionEditor mistake={mistake} onDone={() => setEditing(false)} />;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <p className="text-xs text-muted-foreground">{mistake.source ?? "No source noted"}</p>
        <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
          Edit question
        </Button>
      </div>

      <p className="leading-relaxed whitespace-pre-line">{mistake.question_text}</p>

      {mistake.choices && (
        <ol className="space-y-1.5 text-sm text-muted-foreground">
          {mistake.choices.map((choice, index) => (
            <li key={choice}>
              <span className="font-mono">{String.fromCharCode(65 + index)}.</span> {choice}
            </li>
          ))}
        </ol>
      )}

      <Separator />

      <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
        <span>
          <span className="text-muted-foreground">You put </span>
          <span className="font-medium text-destructive">{mistake.your_answer}</span>
        </span>
        <span>
          <span className="text-muted-foreground">Answer </span>
          <span className="font-medium">{mistake.correct_answer}</span>
        </span>
      </div>

      {mistake.student_note && (
        <p className="text-sm text-muted-foreground italic">Your note: {mistake.student_note}</p>
      )}
    </div>
  );
}
