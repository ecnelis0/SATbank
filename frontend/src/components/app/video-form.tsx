"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Offered, not imposed. The tab is the student's own word — these are just the
 *  ones most people reach for, and typing anything else makes that tab. */
const SUGGESTED = ["grammar", "reading", "algebra", "geometry", "vocabulary", "strategy"];

export function VideoForm({ defaultSubject }: { defaultSubject?: string | null }) {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [url, setUrl] = useState("");
  const [subject, setSubject] = useState(defaultSubject ?? "");
  const [directions, setDirections] = useState("");
  const [transcript, setTranscript] = useState("");
  const [showTranscript, setShowTranscript] = useState(false);

  const add = useMutation({
    mutationFn: () =>
      api.addVideo({
        url: url.trim(),
        subject: subject.trim() || null,
        directions: directions.trim() || null,
        transcript: transcript.trim() || null,
      }),
    onSuccess: (video) => {
      queryClient.invalidateQueries({ queryKey: ["videos"] });
      setUrl("");
      setDirections("");
      setTranscript("");
      setShowTranscript(false);
      toast.success("Added. Reading it now — the concepts appear when it is done.");
      router.push(`/videos/${video.id}`);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (url.trim()) add.mutate();
      }}
      className="space-y-4"
    >
      <div>
        <Label htmlFor="video-url">YouTube link</Label>
        <Input
          id="video-url"
          className="mt-1.5"
          placeholder="https://www.youtube.com/watch?v=…"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
        />
      </div>

      <div>
        <Label htmlFor="video-subject">Which tab?</Label>
        <Input
          id="video-subject"
          className="mt-1.5"
          placeholder="grammar"
          value={subject}
          onChange={(event) => setSubject(event.target.value)}
        />
        <div className="mt-2 flex flex-wrap gap-1.5">
          {SUGGESTED.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setSubject(option)}
              className={cn(
                "rounded-full border px-2.5 py-0.5 text-xs transition-colors",
                subject.trim().toLowerCase() === option
                  ? "border-transparent bg-accent text-accent-foreground"
                  : "border-border text-muted-foreground hover:text-foreground",
              )}
            >
              {option}
            </button>
          ))}
        </div>
      </div>

      <div>
        <Label htmlFor="video-directions">Anything the AI should do with it?</Label>
        <Textarea
          id="video-directions"
          rows={3}
          className="mt-1.5"
          placeholder="Optional — e.g. “Only the comma rules, as a checklist I can revise from.”"
          value={directions}
          onChange={(event) => setDirections(event.target.value)}
        />
      </div>

      {showTranscript ? (
        <div>
          <Label htmlFor="video-transcript">Transcript</Label>
          <Textarea
            id="video-transcript"
            rows={5}
            className="mt-1.5"
            placeholder="Paste the transcript here."
            value={transcript}
            onChange={(event) => setTranscript(event.target.value)}
          />
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setShowTranscript(true)}
          // `block`: a bare <button> is inline-level, so `space-y` put no line
          // between this and the submit button and the two ran together.
          className="block text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
        >
          The video has no captions — paste the transcript instead
        </button>
      )}

      <Button type="submit" disabled={add.isPending || !url.trim()}>
        {add.isPending ? "Adding…" : "Add the video"}
      </Button>
    </form>
  );
}
