"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Input } from "@/components/ui/input";
import { api, keys } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Pick labels you have used before, or invent one.
 *
 *  Free strings rather than a managed vocabulary: the point of a label like "by
 *  mistake" is that you can add it the moment you think of it. Existing ones are
 *  offered so the bank does not fill up with three spellings of the same idea. */
export function TagPicker({
  selected,
  onChange,
  disabled = false,
}: {
  selected: string[];
  onChange: (tags: string[]) => void;
  disabled?: boolean;
}) {
  const [draft, setDraft] = useState("");
  const { data: known } = useQuery({ queryKey: keys.tags(), queryFn: api.listTags });

  const chosen = new Set(selected.map((tag) => tag.toLowerCase()));
  const offered = (known ?? []).filter((entry) => !chosen.has(entry.tag.toLowerCase()));

  const add = (tag: string) => {
    const tidy = tag.trim().replace(/\s+/g, " ");
    if (!tidy || chosen.has(tidy.toLowerCase())) return;
    onChange([...selected, tidy]);
    setDraft("");
  };

  return (
    <div className="space-y-2">
      {selected.length > 0 && (
        <ul className="flex flex-wrap gap-1.5">
          {selected.map((tag) => (
            <li key={tag}>
              <span className="inline-flex items-center gap-1 rounded-full border bg-muted/50 py-0.5 pr-1 pl-2.5 text-xs">
                {tag}
                <button
                  type="button"
                  aria-label={`Remove label ${tag}`}
                  disabled={disabled}
                  onClick={() => onChange(selected.filter((item) => item !== tag))}
                  className="rounded-full px-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  ×
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}

      <Input
        value={draft}
        disabled={disabled}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === ",") {
            // Enter here means "add this label", not "submit the whole form".
            event.preventDefault();
            add(draft);
          }
        }}
        placeholder="Your own label — type it and press Enter"
        aria-label="Add a label"
      />

      {offered.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {offered.slice(0, 10).map((entry) => (
            <button
              key={entry.tag}
              type="button"
              disabled={disabled}
              onClick={() => add(entry.tag)}
              className={cn(
                "rounded-full border px-2.5 py-0.5 text-xs transition-colors hover:bg-muted",
                entry.suggested ? "border-dashed text-muted-foreground" : "",
              )}
            >
              {entry.tag}
              {entry.count > 0 && (
                <span className="ml-1 text-muted-foreground">{entry.count}</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
