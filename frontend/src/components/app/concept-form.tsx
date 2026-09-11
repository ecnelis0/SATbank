"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { PendingImages, usePendingImages } from "@/components/app/pending-images";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, keys } from "@/lib/api";
import { SECTION_LABELS } from "@/lib/labels";
import type { Concept, Section } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Math and Reading & Writing first, because they are the answer nearly every time.
 *  "Neither" stays available but has to be chosen: it used to be the default, so the
 *  field was a thing to skip rather than a decision, and concepts piled up unfiled. */
const SECTION_OPTIONS: { value: Section | "none"; label: string }[] = [
  { value: "math", label: SECTION_LABELS.math },
  { value: "reading_writing", label: SECTION_LABELS.reading_writing },
  { value: "none", label: "Neither" },
];

/** Writes a new concept, or edits one in place when `concept` is given. */
export function ConceptForm({
  concept,
  onDone,
}: {
  concept?: Concept;
  onDone?: (concept: Concept) => void;
}) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState(concept?.title ?? "");
  const [body, setBody] = useState(concept?.body ?? "");
  // Unset, not "none": an unanswered question and an answer of "neither" are
  // different things, and only one of them should be possible by accident.
  const [section, setSection] = useState<Section | "none" | null>(
    concept ? (concept.section ?? "none") : null,
  );
  // Only when writing a new one: an existing concept uploads straight to its own page.
  const diagrams = usePendingImages();

  const save = useMutation({
    mutationFn: async () => {
      const draft = {
        title: title.trim(),
        body: body.trim() || null,
        section: section === "none" || section === null ? null : section,
      };
      if (concept) return api.updateConcept(concept.id, draft);

      const created = await api.createConcept(draft);
      // Diagrams go up after the concept exists, one at a time so their order is the
      // order they were dropped. A failed upload must not lose the concept itself.
      let failed = 0;
      for (const diagram of diagrams.images) {
        try {
          await api.uploadConceptImage(created.id, diagram.file);
        } catch {
          failed += 1;
        }
      }
      if (failed > 0) {
        toast.error(
          `Concept saved, but ${failed} diagram${failed === 1 ? "" : "s"} would not ` +
            "upload. Add them again from the concept.",
        );
      }
      return created;
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: keys.concepts() });
      queryClient.invalidateQueries({ queryKey: keys.concept(saved.id) });
      queryClient.invalidateQueries({ queryKey: keys.stats() });
      if (!concept) {
        setTitle("");
        setBody("");
        setSection(null);
        diagrams.clear();
      }
      toast.success(concept ? "Saved." : "Concept added.");
      onDone?.(saved);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (title.trim()) save.mutate();
      }}
    >
      <div>
        <Label htmlFor="concept-title">The concept</Label>
        <Input
          id="concept-title"
          className="mt-1.5"
          placeholder="Circumference gives you the radius first"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
        />
      </div>

      <div>
        <Label htmlFor="concept-body">In your own words</Label>
        <Textarea
          id="concept-body"
          rows={5}
          className="mt-1.5"
          placeholder="What it is, why it keeps catching you, and what to do about it."
          value={body}
          onChange={(event) => setBody(event.target.value)}
        />
      </div>

      {!concept && (
        <div>
          <Label htmlFor="concept-diagrams">Diagrams</Label>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Optional. A figure, a worked example, a photo of the rule.
          </p>
          <div id="concept-diagrams" className="mt-1.5">
            <PendingImages
              images={diagrams.images}
              onAdd={diagrams.add}
              onRemove={diagrams.remove}
              disabled={save.isPending}
            />
          </div>
        </div>
      )}

      <fieldset>
        <legend className="text-sm font-medium">Which section?</legend>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Concepts are filed under their section, and the side rail expands to show
          them there.
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          {SECTION_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              aria-pressed={section === option.value}
              onClick={() => setSection(option.value)}
              className={cn(
                "rounded-md border px-3 py-1.5 text-sm transition-colors",
                section === option.value
                  ? "border-primary bg-primary text-primary-foreground"
                  : "hover:bg-muted",
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
      </fieldset>

      <div className="flex gap-2">
        <Button
          type="submit"
          disabled={save.isPending || !title.trim() || section === null}
        >
          {save.isPending ? "Saving…" : concept ? "Save" : "Add concept"}
        </Button>
        {section === null && title.trim() && (
          <p className="self-center text-xs text-muted-foreground">
            Pick a section first.
          </p>
        )}
        {concept && onDone && (
          <Button type="button" variant="ghost" onClick={() => onDone(concept)}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}
