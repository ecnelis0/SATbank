"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useSyncExternalStore } from "react";
import { useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { ConceptPicker } from "@/components/app/concept-picker";
import {
  clearDraft,
  getDraft,
  getServerDraft,
  isWorthKeeping,
  saveChoicesOfFiling,
  saveValues,
  subscribe as subscribeToDraft,
} from "@/components/app/log-draft";
import { PendingImages, usePendingImages } from "@/components/app/pending-images";
import { ScanQuestion } from "@/components/app/scan-question";
import { TagPicker } from "@/components/app/tag-picker";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, keys } from "@/lib/api";
import { SECTION_LABELS, URGENCY_LABELS } from "@/lib/labels";
import type { MistakeDraft, ScannedQuestion, Section } from "@/lib/types";
import { cn } from "@/lib/utils";

const schema = z.object({
  section: z.enum(["reading_writing", "math"]),
  // "ai" means: leave it to the analyzer. Anything else is the student's own call
  // and the analyzer will not overrule it.
  urgency: z.enum(["ai", "fundamental", "very_important", "important"]),
  source: z.string().max(200).optional(),
  question_text: z.string().trim().min(1, "Paste the question you missed."),
  choicesText: z.string().optional(),
  your_answer: z.string().trim().min(1, "What did you put?"),
  correct_answer: z.string().trim().min(1, "What was the right answer?"),
  student_note: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

/** A label the page printed in front of a choice: "A)", "(B)", "C.", "D:".
 *
 *  Deliberately narrow. It has to have a separator *and* something after it, so a
 *  question whose choices are the bare letters A-D keeps them, and it stops at H so
 *  roman-numeral choices ("I)", "II)") are never mistaken for a label. */
const CHOICE_LABEL = /^\(?([A-Ha-h])[).:\]]\s*(.+)$/;

/** One choice per line, labelled or not; blank lines are spacing, not data.
 *
 *  The label is stripped because the app draws its own A/B/C/D everywhere it shows
 *  a question — keeping the typed one renders "A. A. The LINE transposon…". */
export function parseChoices(text: string | undefined): string[] | null {
  const lines = (text ?? "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const labelled = CHOICE_LABEL.exec(line);
      return labelled ? labelled[2].trim() : line;
    })
    .filter(Boolean);
  return lines.length > 0 ? lines : null;
}

/** The other direction: bare choices laid out the way the box shows them, one
 *  labelled choice per block with a blank line between, so four options are four
 *  things to read rather than a wall. */
export function formatChoices(choices: string[]): string {
  return choices
    .map((choice, index) => `${String.fromCharCode(65 + index)}) ${choice.trim()}`)
    .join("\n\n");
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <p className="mt-1 text-sm text-destructive">{message}</p>;
}

const EMPTY_FORM: FormValues = {
  section: "math",
  urgency: "ai",
  question_text: "",
  choicesText: "",
  your_answer: "",
  correct_answer: "",
  source: "",
  student_note: "",
};

export function MistakeForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const pictures = usePendingImages();
  // Tags and concepts are rendered straight from the draft store, so picking one
  // is a write and never a piece of component state to keep in step with it.
  const stored = useSyncExternalStore(subscribeToDraft, getDraft, getServerDraft);
  const tags = stored.tags;
  const conceptIds = stored.conceptIds;
  const setTags = (next: string[]) => saveChoicesOfFiling({ tags: next });
  const setConceptIds = (next: string[]) => saveChoicesOfFiling({ conceptIds: next });

  const {
    control,
    register,
    handleSubmit,
    setValue,
    setFocus,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: EMPTY_FORM,
  });

  // Put the typed fields back, once, after mount. Reading localStorage during
  // render instead would hand the server one set of values and the browser
  // another, and hydration would throw the restored draft away again. `reset` is
  // react-hook-form's own API rather than component state, which is what keeps
  // this out of the set-state-in-an-effect rule.
  useEffect(() => {
    const saved = getDraft();
    if (isWorthKeeping(saved)) {
      reset({ ...EMPTY_FORM, ...(saved.values as Partial<FormValues>) });
    }
  }, [reset]);

  const clearEverything = () => {
    reset(EMPTY_FORM);
    pictures.clear();
    clearDraft();
  };

  // `useWatch` rather than `watch()` for rendering: the latter returns a fresh
  // function each render, which opts this component out of the React Compiler's
  // memoization. The subscription form of `watch` above is a different thing —
  // it never reads into the render.
  const section = useWatch({ control, name: "section" });
  const draftValues = useWatch({ control });
  const urgency = useWatch({ control, name: "urgency" });

  // Every change, straight to storage. Debouncing would mean the last few
  // characters typed are the ones lost, which is the case the draft exists for.
  //
  // The guard is about ordering, not about saving effort: on the first commit
  // this effect runs with the empty values the form rendered with, a beat before
  // the restore above has taken effect, and without it that empty form would be
  // written straight over the draft it is in the middle of restoring. An empty
  // form never replaces a draft that has something in it — clearing is what the
  // Clear everything button is for.
  useEffect(() => {
    const next = { values: draftValues as Record<string, unknown>, tags, conceptIds };
    if (!isWorthKeeping(next) && isWorthKeeping(getDraft())) return;
    saveValues(next.values);
  }, [draftValues, tags, conceptIds]);


  /** Fill the form from a picture the AI has read.

      Only fields the reader actually returned are written, so a null in the
      scan never wipes something typed first. `your_answer` is never among them
      - a picture cannot know it - so the cursor goes there, which is both the
      next thing to do and the whole point of the bank. */
  const fillFromPicture = (scanned: ScannedQuestion, file: File) => {
    setValue("question_text", scanned.question_text, { shouldValidate: true });
    if (scanned.choices?.length) setValue("choicesText", formatChoices(scanned.choices));
    if (scanned.correct_answer)
      setValue("correct_answer", scanned.correct_answer, { shouldValidate: true });
    if (scanned.section) setValue("section", scanned.section);
    if (scanned.source) setValue("source", scanned.source);
    // Attached to the question too, so the original sits beside the AI's reading
    // of it rather than being thrown away once the fields are filled.
    pictures.add([file]);
    setFocus("your_answer");
  };

  const log = useMutation({
    mutationFn: async ({ draft, analyze }: { draft: MistakeDraft; analyze: boolean }) => {
      const mistake = await api.logMistake(draft, analyze);

      // Pictures go up after the question exists, one at a time so their order is
      // the order they were dropped. A failure here must not cost the question:
      // it is already saved and already on the ladder, so report and carry on.
      let failed = 0;
      for (const picture of pictures.images) {
        try {
          await api.uploadImage(mistake.id, picture.file);
        } catch {
          failed += 1;
        }
      }
      return { mistake, failed };
    },
    onSuccess: ({ mistake, failed }) => {
      queryClient.invalidateQueries({ queryKey: ["mistakes"] });
      queryClient.invalidateQueries({ queryKey: keys.stats() });
      queryClient.invalidateQueries({ queryKey: ["reviews"] });
      pictures.clear();
      reset(EMPTY_FORM);
      clearDraft();
      if (failed > 0) {
        toast.error(
          `Logged, but ${failed} picture${failed === 1 ? "" : "s"} would not upload. ` +
            "Add them again from the question.",
        );
      } else {
        toast.success("Logged. First review in an hour.");
      }
      router.push(`/bank/${mistake.id}`);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const submitWith = (analyze: boolean) =>
    handleSubmit((values) =>
      log.mutate({
        analyze,
        draft: {
          section: values.section,
          urgency: values.urgency === "ai" ? null : values.urgency,
          tags,
          concept_ids: conceptIds,
          source: values.source?.trim() || null,
          question_text: values.question_text.trim(),
          choices: parseChoices(values.choicesText),
          your_answer: values.your_answer.trim(),
          correct_answer: values.correct_answer.trim(),
          student_note: values.student_note?.trim() || null,
        },
      }),
    );

  return (
    <form onSubmit={submitWith(true)} className="space-y-6" noValidate>
      <ScanQuestion
        onScanned={fillFromPicture}
        onKeepPicture={(file) => pictures.add([file])}
        disabled={log.isPending}
      />

      <fieldset>
        <legend className="text-sm font-medium">Section</legend>
        <div className="mt-2 flex gap-2">
          {(Object.keys(SECTION_LABELS) as Section[]).map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={section === value}
              onClick={() => setValue("section", value)}
              className={cn(
                "rounded-md border px-3 py-1.5 text-sm transition-colors",
                section === value
                  ? "border-primary bg-primary text-primary-foreground"
                  : "hover:bg-muted",
              )}
            >
              {SECTION_LABELS[value]}
            </button>
          ))}
        </div>
      </fieldset>

      <div>
        <Label htmlFor="source">Where it came from</Label>
        <Input
          id="source"
          placeholder="Bluebook Practice Test 4, Q17"
          className="mt-1.5"
          {...register("source")}
        />
      </div>

      <div>
        <Label htmlFor="question_text">The question</Label>
        <Textarea
          id="question_text"
          rows={5}
          placeholder="Paste the question exactly as it appeared."
          className="mt-1.5"
          {...register("question_text")}
        />
        <FieldError message={errors.question_text?.message} />
      </div>

      <div>
        <Label htmlFor="choicesText">Answer choices</Label>
        <Textarea
          id="choicesText"
          rows={7}
          placeholder={"Optional — one per line, a blank line between\n\nA) 3\n\nB) 5\n\nC) 7\n\nD) 15"}
          className="mt-1.5"
          {...register("choicesText")}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <Label htmlFor="your_answer">You put</Label>
          <Input id="your_answer" className="mt-1.5" {...register("your_answer")} />
          <FieldError message={errors.your_answer?.message} />
        </div>
        <div>
          <Label htmlFor="correct_answer">The answer was</Label>
          <Input id="correct_answer" className="mt-1.5" {...register("correct_answer")} />
          <FieldError message={errors.correct_answer?.message} />
        </div>
      </div>

      <fieldset>
        <legend className="text-sm font-medium">How urgent is this?</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {(
            [
              ["ai", "Let the AI decide"],
              ["fundamental", URGENCY_LABELS.fundamental],
              ["very_important", URGENCY_LABELS.very_important],
              ["important", URGENCY_LABELS.important],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              aria-pressed={urgency === value}
              onClick={() => setValue("urgency", value)}
              className={cn(
                "rounded-md border px-3 py-1.5 text-sm transition-colors",
                urgency === value
                  ? "border-primary bg-primary text-primary-foreground"
                  : "hover:bg-muted",
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </fieldset>

      <div>
        <Label htmlFor="labels">Your labels</Label>
        <div id="labels" className="mt-1.5">
          <TagPicker selected={tags} onChange={setTags} disabled={log.isPending} />
        </div>
      </div>

      <div>
        <Label htmlFor="concepts">File under a concept</Label>
        <div id="concepts" className="mt-1.5">
          <ConceptPicker
            selected={conceptIds}
            onChange={setConceptIds}
            disabled={log.isPending}
          />
        </div>
      </div>

      <div>
        <Label htmlFor="pictures">Pictures</Label>
        <div id="pictures" className="mt-1.5">
          <PendingImages
            images={pictures.images}
            onAdd={pictures.add}
            onRemove={pictures.remove}
            disabled={log.isPending}
          />
        </div>
      </div>

      <div>
        <Label htmlFor="student_note">What happened?</Label>
        <Textarea
          id="student_note"
          rows={3}
          placeholder="Optional, and the most useful box on this page — the analysis leans on it."
          className="mt-1.5"
          {...register("student_note")}
        />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={log.isPending}>
          {log.isPending
            ? pictures.images.length > 0
              ? "Logging and uploading…"
              : "Logging…"
            : "Log it and ask the AI"}
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={log.isPending}
          onClick={submitWith(false)}
        >
          Just log it
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={log.isPending}
          onClick={clearEverything}
          className="text-muted-foreground"
        >
          Clear everything
        </Button>
        <p className="text-xs text-muted-foreground">
          Either way the review ladder starts now. What you type is kept if you leave the
          page — screenshots excepted, they are too big to hold. You can ask for the
          debrief, or write your own, at any point.
        </p>
      </div>
    </form>
  );
}
