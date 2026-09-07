"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, keys } from "@/lib/api";
import { SECTION_LABELS } from "@/lib/labels";
import type { MistakeDraft, Section } from "@/lib/types";
import { cn } from "@/lib/utils";

const schema = z.object({
  section: z.enum(["reading_writing", "math"]),
  source: z.string().max(200).optional(),
  question_text: z.string().trim().min(1, "Paste the question you missed."),
  choicesText: z.string().optional(),
  your_answer: z.string().trim().min(1, "What did you put?"),
  correct_answer: z.string().trim().min(1, "What was the right answer?"),
  student_note: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

/** One choice per line; blank lines are the student's formatting, not data. */
export function parseChoices(text: string | undefined): string[] | null {
  const lines = (text ?? "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  return lines.length > 0 ? lines : null;
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <p className="mt-1 text-sm text-destructive">{message}</p>;
}

export function MistakeForm() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const {
    control,
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { section: "math" },
  });

  // `useWatch` rather than `watch()`: the latter returns a fresh function each
  // render, which opts this component out of the React Compiler's memoization.
  const section = useWatch({ control, name: "section" });

  const log = useMutation({
    mutationFn: ({ draft, analyze }: { draft: MistakeDraft; analyze: boolean }) =>
      api.logMistake(draft, analyze),
    onSuccess: (mistake) => {
      queryClient.invalidateQueries({ queryKey: ["mistakes"] });
      queryClient.invalidateQueries({ queryKey: keys.stats() });
      queryClient.invalidateQueries({ queryKey: ["reviews"] });
      toast.success("Logged. First review in an hour.");
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
          rows={4}
          placeholder={"One per line — optional\n3\n5\n7\n15"}
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
          {log.isPending ? "Logging…" : "Log it and ask the AI"}
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={log.isPending}
          onClick={submitWith(false)}
        >
          Just log it
        </Button>
        <p className="text-xs text-muted-foreground">
          Either way the review ladder starts now. You can ask for the debrief, or write
          your own, at any point.
        </p>
      </div>
    </form>
  );
}
