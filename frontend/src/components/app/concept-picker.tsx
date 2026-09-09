"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { api, keys } from "@/lib/api";
import { SECTION_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";

/** File a question under concepts while logging it, rather than only afterwards. */
export function ConceptPicker({
  selected,
  onChange,
  disabled = false,
}: {
  selected: string[];
  onChange: (conceptIds: string[]) => void;
  disabled?: boolean;
}) {
  const { data: concepts } = useQuery({
    queryKey: keys.concepts(),
    queryFn: api.listConcepts,
  });

  if (!concepts) return null;

  if (concepts.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No concepts written yet.{" "}
        <Link href="/concepts" className="underline">
          Write one
        </Link>{" "}
        and you can file questions under it as you log them.
      </p>
    );
  }

  const toggle = (id: string) =>
    onChange(
      selected.includes(id) ? selected.filter((item) => item !== id) : [...selected, id],
    );

  return (
    <div className="flex flex-wrap gap-1.5">
      {concepts.map((concept) => {
        const on = selected.includes(concept.id);
        return (
          <button
            key={concept.id}
            type="button"
            aria-pressed={on}
            disabled={disabled}
            onClick={() => toggle(concept.id)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs transition-colors",
              on ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted",
            )}
          >
            {concept.title}
            {concept.section && (
              <span className={cn("ml-1", on ? "opacity-70" : "text-muted-foreground")}>
                {SECTION_LABELS[concept.section]}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
