"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { useQuestionChat } from "@/components/app/question-chat";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api, keys } from "@/lib/api";
import type { Mistake, Turn } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Talk to the debrief itself: say what happened, or what it got wrong, and it is
 *  rewritten from the question, your answer, your note and everything said here -
 *  re-filed under a new reason if that is what you told it.
 *
 *  Unlike the ask-about-this-question chat, this conversation is kept: it is the
 *  record of why the debrief says what it says, and the whole-bank analysis
 *  reads it. */
export function DebriefChat({ mistake }: { mistake: Mistake }) {
  const queryClient = useQueryClient();
  // The ask chat's thread, shared: what was worked out there goes with a message
  // sent here, and a rewrite made here is announced there.
  const chat = useQuestionChat();
  const [message, setMessage] = useState("");
  // Shown at once, before the round trip: the rewrite takes seconds, and a box
  // that empties with nothing in its place reads as a message thrown away.
  const [sending, setSending] = useState<string | null>(null);

  const { data: turns, isError } = useQuery({
    queryKey: keys.debrief(mistake.id),
    queryFn: () => api.debriefConversation(mistake.id),
  });

  const talk = useMutation({
    mutationFn: ({ text, context }: { text: string; context: Turn[] }) =>
      api.talkToDebrief(mistake.id, text, context),
    onSuccess: (exchange, { context }) => {
      // The ask chat's turns sent along are now kept with the debrief.
      const keptThrough = chat.keptUpTo + context.length;
      const reply = [...exchange.turns].reverse().find((t) => t.role === "assistant");
      if (!exchange.error && reply && chat.thread.length > 0) {
        // Tell the other box, if there is a conversation going on in it.
        const at = chat.thread.length;
        chat.setThread((current) => [
          ...current,
          { role: "assistant", text: `From “Talk to the debrief”: ${reply.text}` },
        ]);
        chat.setUpdates((current) => [...current, at]);
        chat.setKeptUpTo(at + 1);
      } else {
        chat.setKeptUpTo(keptThrough);
      }
      queryClient.setQueryData(keys.debrief(mistake.id), exchange.turns);
      queryClient.setQueryData(keys.mistake(mistake.id), exchange.mistake);
      queryClient.invalidateQueries({ queryKey: ["mistakes"] });
      queryClient.invalidateQueries({ queryKey: keys.stats() });
      if (exchange.error) {
        toast.error("The debrief could not be rewritten just now. Your message is saved.");
      }
    },
    onError: (error: Error, { text }) => {
      // Nothing reached the API, so nothing was saved: put it back to send again.
      setMessage(text);
      toast.error(error.message);
    },
    onSettled: () => setSending(null),
  });

  const send = () => {
    const trimmed = message.trim();
    if (!trimmed || talk.isPending) return;
    setSending(trimmed);
    setMessage("");
    talk.mutate({ text: trimmed, context: chat.thread.slice(chat.keptUpTo) });
  };

  const shown = turns ?? [];

  return (
    <div className="space-y-3 border-t border-foreground/10 pt-4">
      <div className="space-y-1">
        <h3 className="text-sm font-medium">Talk to the debrief</h3>
        <p className="text-xs text-muted-foreground">
          Say what really happened or what to change. It rewrites the debrief and
          re-files the question, and keeps this conversation.
        </p>
      </div>

      {isError && (
        <p className="text-xs text-destructive" role="alert">
          The earlier conversation could not be loaded. Nothing has been lost.
        </p>
      )}

      {(shown.length > 0 || sending) && (
        <ol className="space-y-2" aria-label="Conversation with the debrief">
          {shown.map((turn) => (
            <li
              key={turn.id}
              className={cn(
                "max-w-[42rem] rounded-2xl px-4 py-2 text-sm leading-relaxed whitespace-pre-wrap",
                turn.role === "student"
                  ? "ml-auto w-fit bg-primary text-primary-foreground"
                  : "border border-malachite-deep/20 bg-accent text-accent-foreground",
              )}
            >
              {turn.text}
            </li>
          ))}
          {sending && (
            <li className="ml-auto w-fit max-w-[42rem] rounded-2xl bg-primary/80 px-4 py-2 text-sm whitespace-pre-wrap text-primary-foreground">
              {sending}
            </li>
          )}
        </ol>
      )}

      {talk.isPending && (
        <p className="text-xs text-muted-foreground" role="status">
          Rewriting the debrief…
        </p>
      )}

      <form
        className="space-y-2"
        onSubmit={(event) => {
          event.preventDefault();
          send();
        }}
      >
        <Textarea
          rows={2}
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              send();
            }
          }}
          placeholder="e.g. I misread it as 3x — and I'd like the steps shorter."
          aria-label="Tell the debrief"
        />
        <Button type="submit" size="sm" disabled={talk.isPending || !message.trim()}>
          {talk.isPending ? "Rewriting…" : "Send to the debrief"}
        </Button>
      </form>
    </div>
  );
}
