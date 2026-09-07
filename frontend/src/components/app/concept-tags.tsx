"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { api, keys } from "@/lib/api";
import type { Mistake } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Tag a question with concepts, after the fact. Lives on the question's own page. */
export function ConceptTags({ mistake }: { mistake: Mistake }) {
  const queryClient = useQueryClient();
  const [picking, setPicking] = useState(false);

  const { data: concepts } = useQuery({
    queryKey: keys.concepts(),
    queryFn: api.listConcepts,
    enabled: picking,
  });

  const settle = () => {
    queryClient.invalidateQueries({ queryKey: keys.mistake(mistake.id) });
    queryClient.invalidateQueries({ queryKey: ["mistakes"] });
    queryClient.invalidateQueries({ queryKey: keys.concepts() });
    queryClient.invalidateQueries({ queryKey: keys.stats() });
  };

  const tag = useMutation({
    mutationFn: (conceptId: string) => api.tagQuestion(conceptId, mistake.id),
    onSuccess: (updated) => {
      settle();
      queryClient.invalidateQueries({ queryKey: keys.concept(updated.id) });
      toast.success("Tagged.");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const untag = useMutation({
    mutationFn: (conceptId: string) => api.untagQuestion(conceptId, mistake.id),
    onSuccess: (updated) => {
      settle();
      queryClient.invalidateQueries({ queryKey: keys.concept(updated.id) });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const tagged = new Set(mistake.concepts.map((concept) => concept.id));
  const untagged = (concepts ?? []).filter((concept) => !tagged.has(concept.id));

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-medium">Concepts</h2>
        <Button
          size="sm"
          variant="ghost"
          className="ml-auto"
          onClick={() => setPicking(!picking)}
        >
          {picking ? "Done" : "Tag with a concept"}
        </Button>
      </div>

      {mistake.concepts.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Not filed under any concept yet.
        </p>
      ) : (
        <ul className="flex flex-wrap gap-1.5">
          {mistake.concepts.map((concept) => (
            <li key={concept.id}>
              <span className="inline-flex items-center gap-1 rounded-full border bg-muted/50 py-0.5 pr-1 pl-2.5 text-xs">
                <Link href={`/concepts/${concept.id}`} className="hover:underline">
                  {concept.title}
                </Link>
                <button
                  type="button"
                  aria-label={`Remove ${concept.title}`}
                  disabled={untag.isPending}
                  onClick={() => untag.mutate(concept.id)}
                  className="rounded-full px-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  ×
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}

      {picking && (
        <div className="space-y-1.5 rounded-lg border p-2">
          {untagged.length === 0 ? (
            <p className="px-2 py-1.5 text-sm text-muted-foreground">
              {concepts && concepts.length > 0
                ? "Already tagged with every concept you have written."
                : "No concepts written yet."}{" "}
              <Link href="/concepts" className="underline">
                Write one
              </Link>
              .
            </p>
          ) : (
            untagged.map((concept) => (
              <button
                key={concept.id}
                type="button"
                disabled={tag.isPending}
                onClick={() => tag.mutate(concept.id)}
                className={cn(
                  "block w-full rounded-md px-2 py-1.5 text-left text-sm transition-colors",
                  "hover:bg-muted disabled:opacity-50",
                )}
              >
                {concept.title}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
