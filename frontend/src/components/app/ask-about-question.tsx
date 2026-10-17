"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { useQuestionChat } from "@/components/app/question-chat";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api, keys } from "@/lib/api";
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

/** Sent by the button when the box is empty: apply the chat as it stands. */
const APPLY_AS_IS = "Consider this conversation in the debrief.";

export function AskAboutQuestion({ mistake }: { mistake: Mistake }) {
  const queryClient = useQueryClient();
  // Shared with "Talk to the debrief" - see question-chat.tsx.
  const { thread, setThread, keptUpTo, setKeptUpTo, updates, setUpdates } =
    useQuestionChat();
  const [question, setQuestion] = useState("");
  const foot = useRef<HTMLDivElement>(null);

  const ask = useMutation({
    mutationFn: ({
      asked,
      history,
      apply,
      kept,
    }: {
      asked: string;
      history: Turn[];
      apply: boolean;
      kept: number;
    }) => api.askAboutMistake(mistake.id, asked, history, apply, kept),
  });

  const send = (asked: string, apply = false) => {
    const trimmed = asked.trim();
    if (!trimmed || ask.isPending) return;

    // The history sent is what was on screen *before* this question: the API
    // appends the new one itself, and sending it twice makes the model answer
    // a question it has already been asked.
    // The whole thread goes, so the tutor never forgets the start of its own
    // conversation; `kept` tells the API which turns the debrief already holds.
    const history = thread;
    const asking = [...thread, { role: "student" as const, text: trimmed }];
    setThread(asking);
    setQuestion("");

    ask.mutate(
      { asked: trimmed, history, apply, kept: keptUpTo },
      {
        onSuccess: (reply) => {
          setThread((current) => [...current, { role: "assistant", text: reply.answer }]);
          if (reply.mistake) {
            // It was taken as a command. Whether or not the rewrite worked, what
            // was said is now kept with the debrief.
            setKeptUpTo(asking.length + 1);
            queryClient.invalidateQueries({ queryKey: keys.debrief(mistake.id) });
          }
          if (reply.debrief_updated && reply.mistake) {
            setUpdates((current) => [...current, asking.length]);
            queryClient.setQueryData(keys.mistake(mistake.id), reply.mistake);
            queryClient.invalidateQueries({ queryKey: ["mistakes"] });
            queryClient.invalidateQueries({ queryKey: keys.stats() });
          }
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
              {updates.includes(index) && (
                <span className="mb-1 block text-[11px] font-medium tracking-wide uppercase opacity-70">
                  Debrief updated
                </span>
              )}
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
          placeholder="Ask about this question — or say “consider this in the debrief”…"
          aria-label="Ask about this question"
        />
        <div className="flex items-center gap-3">
          <Button type="submit" size="sm" disabled={ask.isPending || !question.trim()}>
            {ask.isPending ? "Asking…" : "Ask"}
          </Button>
          {(thread.length > keptUpTo || question.trim()) && (
            <Button
              type="button"
              size="sm"
              variant="secondary"
              disabled={ask.isPending}
              onClick={() => send(question.trim() || APPLY_AS_IS, true)}
            >
              Apply to the debrief
            </Button>
          )}
          {thread.length > 0 && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="text-muted-foreground"
              onClick={() => {
                setThread([]);
                setKeptUpTo(0);
                setUpdates([]);
              }}
            >
              Start again
            </Button>
          )}
        </div>
      </form>
    </div>
  );
}
