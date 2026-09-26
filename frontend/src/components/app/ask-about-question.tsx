"use client";

import { useMutation } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import type { Mistake, Turn } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Openers worth a tap. The first is the one the whole panel exists for: a
 *  debrief written in the app's own vocabulary is no use if a word in it is the
 *  part you did not follow. */
const OPENERS = [
  "What does this debrief mean?",
  "Why is my answer wrong?",
  "How do I do this next time?",
];

export function AskAboutQuestion({ mistake }: { mistake: Mistake }) {
  const [thread, setThread] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const foot = useRef<HTMLDivElement>(null);

  const ask = useMutation({
    mutationFn: ({ asked, history }: { asked: string; history: Turn[] }) =>
      api.askAboutMistake(mistake.id, asked, history),
  });

  const send = (asked: string) => {
    const trimmed = asked.trim();
    if (!trimmed || ask.isPending) return;

    // The history sent is what was on screen *before* this question: the API
    // appends the new one itself, and sending it twice makes the model answer
    // a question it has already been asked.
    const history = thread;
    setThread([...history, { role: "student", text: trimmed }]);
    setQuestion("");

    ask.mutate(
      { asked: trimmed, history },
      {
        onSuccess: (reply) => {
          setThread((current) => [...current, { role: "assistant", text: reply.answer }]);
          // Optional call: scrolling is a nicety, and it is not worth throwing
          // out of the success path in an environment that has no implementation
          // of it (jsdom has none).
          foot.current?.scrollIntoView?.({ behavior: "smooth", block: "nearest" });
        },
        onError: (error: Error) => {
          setThread((current) => [
            ...current,
            { role: "assistant", text: `That did not go through — ${error.message}` },
          ]);
        },
      },
    );
  };

  return (
    <div className="space-y-4">
      {thread.length > 0 && (
        <div className="space-y-3">
          {thread.map((turn, index) => (
            <div
              key={index}
              className={cn(
                "max-w-[42rem] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap",
                turn.role === "student"
                  ? "ml-auto bg-primary text-primary-foreground"
                  : "border border-malachite-deep/20 bg-accent text-accent-foreground",
              )}
            >
              {turn.text}
            </div>
          ))}
          {ask.isPending && (
            <p className="text-xs text-muted-foreground" role="status">
              Thinking…
            </p>
          )}
          <div ref={foot} />
        </div>
      )}

      {thread.length === 0 && (
        <div className="flex flex-wrap gap-2">
          {OPENERS.map((opener) => (
            <Button
              key={opener}
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => send(opener)}
            >
              {opener}
            </Button>
          ))}
        </div>
      )}

      <form
        onSubmit={(event) => {
          event.preventDefault();
          send(question);
        }}
        className="space-y-2"
      >
        <Textarea
          rows={2}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              send(question);
            }
          }}
          placeholder="Ask about this question…"
          aria-label="Ask about this question"
        />
        <div className="flex items-center gap-3">
          <Button type="submit" size="sm" disabled={ask.isPending || !question.trim()}>
            {ask.isPending ? "Asking…" : "Ask"}
          </Button>
          {thread.length > 0 && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="text-muted-foreground"
              onClick={() => setThread([])}
            >
              Start again
            </Button>
          )}
        </div>
      </form>
    </div>
  );
}
