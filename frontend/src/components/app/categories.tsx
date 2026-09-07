"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { UrgencyBadge } from "@/components/app/urgency-badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, keys } from "@/lib/api";
import {
  countSelected,
  has,
  isEmpty,
  toSearchParams,
  toggle,
  type Facets,
  NO_FACETS,
} from "@/lib/facets";
import { ERROR_TYPE_LABELS, SECTION_LABELS } from "@/lib/labels";
import { URGENCIES, type ErrorType, type Section } from "@/lib/types";
import { cn } from "@/lib/utils";

function Check({ on }: { on: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        "flex size-4 shrink-0 items-center justify-center rounded border text-[10px]",
        on ? "border-primary bg-primary text-primary-foreground" : "border-border",
      )}
    >
      {on ? "✓" : ""}
    </span>
  );
}

function Item({
  label,
  count,
  selected,
  onToggle,
  indent = false,
}: {
  label: React.ReactNode;
  count: number;
  selected: boolean;
  onToggle: () => void;
  indent?: boolean;
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={selected}
      onClick={onToggle}
      className={cn(
        "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors hover:bg-muted",
        indent && "pl-7",
      )}
    >
      <Check on={selected} />
      <span className="min-w-0 flex-1 truncate">{label}</span>
      <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{count}</span>
    </button>
  );
}

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-1 px-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {title}
      </h3>
      <div className="space-y-0.5">{children}</div>
    </section>
  );
}

/** The browsing half of the rail: every facet, multi-selectable, topics folded
 *  under the section they belong to. */
export function Categories() {
  const router = useRouter();
  const [facets, setFacets] = useState<Facets>(NO_FACETS);
  const [expanded, setExpanded] = useState<Section[]>([]);

  const { data, isPending } = useQuery({ queryKey: keys.stats(), queryFn: api.stats });
  const { data: concepts } = useQuery({
    queryKey: keys.concepts(),
    queryFn: api.listConcepts,
  });

  if (isPending) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-5 w-full" />
        <Skeleton className="h-5 w-full" />
        <Skeleton className="h-5 w-2/3" />
      </div>
    );
  }
  if (!data) return null;

  const countOf = (slots: { key: string; count: number }[], key: string) =>
    slots.find((slot) => slot.key === key)?.count ?? 0;

  const selected = countSelected(facets);
  const sections = Object.keys(SECTION_LABELS) as Section[];

  return (
    <div className="space-y-5">
      <Group title="How urgent">
        {URGENCIES.map((urgency) => (
          <Item
            key={urgency}
            label={<UrgencyBadge urgency={urgency} />}
            count={countOf(data.by_urgency, urgency)}
            selected={has(facets, "urgency", urgency)}
            onToggle={() => setFacets(toggle(facets, "urgency", urgency))}
          />
        ))}
      </Group>

      <Group title="Section & topic">
        {sections.map((section) => {
          const topics = data.topics.filter((entry) => entry.section === section);
          const open = expanded.includes(section);
          return (
            <div key={section}>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  aria-label={`${open ? "Collapse" : "Expand"} ${SECTION_LABELS[section]}`}
                  aria-expanded={open}
                  disabled={topics.length === 0}
                  onClick={() =>
                    setExpanded(
                      open
                        ? expanded.filter((value) => value !== section)
                        : [...expanded, section],
                    )
                  }
                  className="flex size-6 shrink-0 items-center justify-center rounded text-xs text-muted-foreground transition-colors hover:bg-muted disabled:opacity-30"
                >
                  {open ? "▾" : "▸"}
                </button>
                <div className="min-w-0 flex-1">
                  <Item
                    label={SECTION_LABELS[section]}
                    count={countOf(data.by_section, section)}
                    selected={has(facets, "section", section)}
                    onToggle={() => setFacets(toggle(facets, "section", section))}
                  />
                </div>
              </div>

              {open &&
                topics.map((entry) => (
                  <Item
                    key={`${entry.section}:${entry.topic}`}
                    label={entry.topic}
                    count={entry.count}
                    indent
                    selected={has(facets, "topics", entry.topic)}
                    onToggle={() => setFacets(toggle(facets, "topics", entry.topic))}
                  />
                ))}
            </div>
          );
        })}
      </Group>

      {concepts && concepts.length > 0 && (
        <Group title="Concepts">
          {concepts.map((concept) => (
            <Item
              key={concept.id}
              label={
                <span className="flex items-center gap-1.5">
                  <span className="truncate">{concept.title}</span>
                  {/* A concept with nothing tagged filters to an empty bank. Saying
                      so here is cheaper than letting them find out by clicking. */}
                  {concept.question_count === 0 && (
                    <span className="shrink-0 text-[10px] text-muted-foreground">
                      nothing tagged
                    </span>
                  )}
                </span>
              }
              count={concept.question_count}
              selected={has(facets, "concept_ids", concept.id)}
              onToggle={() => setFacets(toggle(facets, "concept_ids", concept.id))}
            />
          ))}
          {data.untagged_questions > 0 && (
            <Item
              label={<span className="text-muted-foreground">No concept yet</span>}
              count={data.untagged_questions}
              selected={facets.hasConcept === false}
              onToggle={() =>
                setFacets({
                  ...facets,
                  hasConcept: facets.hasConcept === false ? null : false,
                })
              }
            />
          )}
        </Group>
      )}

      {data.by_error_type.length > 0 && (
        <Group title="Why you missed it">
          {data.by_error_type.map((slot) => (
            <Item
              key={slot.key}
              label={ERROR_TYPE_LABELS[slot.key as ErrorType] ?? slot.key}
              count={slot.count}
              selected={has(facets, "error_type", slot.key)}
              onToggle={() => setFacets(toggle(facets, "error_type", slot.key as ErrorType))}
            />
          ))}
        </Group>
      )}

      <div className="sticky bottom-0 flex items-center gap-2 border-t bg-background pt-3">
        <Button
          size="sm"
          disabled={isEmpty(facets)}
          onClick={() => router.push(`/bank?${toSearchParams(facets).toString()}`)}
        >
          {selected === 0
            ? "Show questions"
            : `Show ${selected} filter${selected === 1 ? "" : "s"}`}
        </Button>
        {selected > 0 && (
          <Button size="sm" variant="ghost" onClick={() => setFacets(NO_FACETS)}>
            Clear
          </Button>
        )}
      </div>
    </div>
  );
}
