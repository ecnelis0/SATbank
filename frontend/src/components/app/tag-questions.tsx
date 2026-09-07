"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { UrgencyBadge } from "@/components/app/urgency-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, keys } from "@/lib/api";
import { SECTION_LABELS } from "@/lib/labels";
import type { ConceptDetail } from "@/lib/types";

/** Tag questions onto a concept from the concept's own page.
 *
 *  The mirror of `ConceptTags`, which does it from the question's page. Both are
 *  wanted: you either start from the question or from the concept. */
export function TagQuestions({ concept }: { concept: ConceptDetail }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [untaggedOnly, setUntaggedOnly] = useState(true);

  const { data: candidates, isPending } = useQuery({
    queryKey: keys.mistakes({ q: search.trim() || undefined }),
    queryFn: () => api.listMistakes({ q: search.trim() || undefined }),
    enabled: open,
  });

  const tag = useMutation({
    mutationFn: (mistakeId: string) => api.tagQuestion(concept.id, mistakeId),
    onSuccess: (updated) => {
      queryClient.setQueryData(keys.concept(concept.id), updated);
      queryClient.invalidateQueries({ queryKey: keys.concepts() });
      queryClient.invalidateQueries({ queryKey: ["mistakes"] });
      queryClient.invalidateQueries({ queryKey: keys.stats() });
      toast.success("Tagged.");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const already = new Set(concept.mistakes.map((mistake) => mistake.id));

  // Rank by overlap with the concept, so the questions it is probably about are the
  // ones you see first rather than whatever was logged most recently.
  const words = concept.title
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((word) => word.length > 3);

  const relevance = (mistake: (typeof candidates extends undefined ? never : NonNullable<typeof candidates>)[number]) => {
    const haystack = [
      mistake.question_text,
      mistake.topic ?? "",
      (mistake.tags ?? []).join(" "),
    ]
      .join(" ")
      .toLowerCase();
    let score = words.filter((word) => haystack.includes(word)).length * 2;
    if (concept.section && mistake.section === concept.section) score += 1;
    return score;
  };

  const available = (candidates ?? [])
    .filter((mistake) => !already.has(mistake.id))
    .filter((mistake) => !untaggedOnly || mistake.concepts.length === 0)
    .map((mistake) => ({ mistake, score: relevance(mistake) }))
    .sort((a, b) => b.score - a.score)
    .map((entry) => entry.mistake);

  return (
    <div className="space-y-3">
      <Button
        variant={open ? "ghost" : "secondary"}
        size="sm"
        onClick={() => setOpen(!open)}
      >
        {open ? "Done tagging" : "Tag questions with this concept"}
      </Button>

      {open && (
        <div className="space-y-2 rounded-lg border p-3">
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search your questions…"
            aria-label="Search your questions"
          />

          <label className="flex items-center gap-2 px-1 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={untaggedOnly}
              onChange={(event) => setUntaggedOnly(event.target.checked)}
            />
            Only questions with no concept yet
          </label>

          {isPending ? (
            <p className="px-1 py-2 text-sm text-muted-foreground">Loading…</p>
          ) : available.length === 0 ? (
            <p className="px-1 py-2 text-sm text-muted-foreground">
              {candidates && candidates.length > 0
                ? "Every question matching that is already tagged."
                : "No questions match."}
            </p>
          ) : (
            <ul className="max-h-72 space-y-1 overflow-y-auto">
              {available.map((mistake) => (
                <li key={mistake.id}>
                  <button
                    type="button"
                    disabled={tag.isPending}
                    onClick={() => tag.mutate(mistake.id)}
                    className="w-full rounded-md px-2 py-1.5 text-left transition-colors hover:bg-muted disabled:opacity-50"
                  >
                    <span className="mb-0.5 flex flex-wrap items-center gap-1.5">
                      {mistake.urgency && <UrgencyBadge urgency={mistake.urgency} />}
                      <span className="text-[11px] text-muted-foreground">
                        {SECTION_LABELS[mistake.section]}
                        {mistake.topic && ` · ${mistake.topic}`}
                      </span>
                    </span>
                    <span className="line-clamp-2 text-sm">{mistake.question_text}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
