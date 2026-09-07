"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { UrgencyBadge } from "@/components/app/urgency-badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { ERROR_TYPE_LABELS, SECTION_LABELS } from "@/lib/labels";
import type { Answer, Mistake } from "@/lib/types";

const EXAMPLES = [
  "Everything very important from Reading in the past 3 months",
  "What is due for review now?",
  "Which concept gaps keep coming back?",
];

function Hit({ mistake }: { mistake: Mistake }) {
  return (
    <Link
      href={`/bank/${mistake.id}`}
      className="block rounded-lg border px-3 py-2 transition-colors hover:bg-muted/50"
    >
      <div className="mb-1 flex flex-wrap items-center gap-1.5">
        {mistake.urgency && <UrgencyBadge urgency={mistake.urgency} />}
        <span className="text-[11px] text-muted-foreground">
          {SECTION_LABELS[mistake.section]}
          {mistake.error_type && ` · ${ERROR_TYPE_LABELS[mistake.error_type]}`}
        </span>
      </div>
      <p className="line-clamp-2 text-sm leading-snug">{mistake.question_text}</p>
    </Link>
  );
}

export function Ask() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<Answer | null>(null);

  const ask = useMutation({
    mutationFn: (asked: string) => api.ask(asked),
    onSuccess: setResult,
  });

  const send = (asked: string) => {
    const trimmed = asked.trim();
    if (!trimmed) return;
    setQuestion(trimmed);
    ask.mutate(trimmed);
  };

  return (
    <div className="space-y-4">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          send(question);
        }}
        className="space-y-2"
      >
        <Textarea
          rows={3}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              send(question);
            }
          }}
          placeholder="Ask about your bank…"
          aria-label="Ask about your bank"
        />
        <Button type="submit" size="sm" disabled={ask.isPending || !question.trim()}>
          {ask.isPending ? "Looking…" : "Ask"}
        </Button>
      </form>

      {!result && !ask.isPending && (
        <div className="space-y-1.5">
          <p className="text-xs text-muted-foreground">Try:</p>
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => send(example)}
              className="block w-full rounded-md border px-3 py-2 text-left text-xs text-muted-foreground transition-colors hover:bg-muted"
            >
              {example}
            </button>
          ))}
        </div>
      )}

      {ask.isError && (
        <p className="text-sm text-destructive">{(ask.error as Error).message}</p>
      )}

      {result && (
        <div className="space-y-3" aria-live="polite">
          {/* The offline assistant returning the whole bank looks exactly like a
              working search that matched everything. Say which one answered. */}
          {result.analyzer === "stub" && (
            <p className="rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground">
              Offline assistant — it matches your topics and concepts by keyword and
              reports counts, but it cannot reason about your bank. Set{" "}
              <code className="font-mono">AI_PROVIDER=claude</code> and your API key in{" "}
              <code className="font-mono">.env</code> for real answers.
            </p>
          )}
          {!result.analyzer_ready && (
            <p className="rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
              {result.analyzer} is selected but its API key is missing, so nothing was
              analysed.
            </p>
          )}
          <p className="text-sm leading-relaxed whitespace-pre-line">{result.answer}</p>

          {/* What it searched for, so a wrong reading of the sentence is visible
              rather than being mistaken for an empty bank. */}
          <p className="text-xs text-muted-foreground">
            Searched: {result.filter_description}
          </p>

          {result.error && (
            <p className="font-mono text-[11px] text-muted-foreground">{result.error}</p>
          )}

          <div className="space-y-2">
            {result.mistakes.map((mistake) => (
              <Hit key={mistake.id} mistake={mistake} />
            ))}
          </div>

          {result.mistakes.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Nothing matched. Try a looser question.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
