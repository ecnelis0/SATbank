"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";

import { ConceptHeader } from "@/components/app/concept-header";
import { Empty } from "@/components/app/empty";
import { MistakeCard } from "@/components/app/mistake-card";
import { Unreachable } from "@/components/app/unreachable";
import { UrgencyBadge } from "@/components/app/urgency-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api, keys } from "@/lib/api";
import {
  fromSearchParams,
  isEmpty,
  toQuery,
  toSearchParams,
  toggle,
  type Facets,
  NO_FACETS,
} from "@/lib/facets";
import { ERROR_TYPE_LABELS, SECTION_LABELS } from "@/lib/labels";
import type { ErrorType, Section, Urgency } from "@/lib/types";

/** One selected facet, with the click that removes it. */
function Pill({ label, onRemove }: { label: React.ReactNode; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border bg-muted/50 py-0.5 pr-1.5 pl-2.5 text-xs">
      {label}
      <button
        type="button"
        onClick={onRemove}
        aria-label="Remove filter"
        className="rounded-full px-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        ×
      </button>
    </span>
  );
}

function BankList() {
  const router = useRouter();
  const params = useSearchParams();

  // The URL is the single source of truth for the facets, so a filtered view is a
  // link, and arriving from the rail or the dashboard needs no syncing effect.
  const selected = useMemo(() => fromSearchParams(params), [params]);
  const [text, setText] = useState(() => params.get("q") ?? "");
  const facets: Facets = { ...selected, text };

  const apply = (next: Facets) => {
    setText(next.text);
    const query = toSearchParams(next).toString();
    router.replace(query ? `/bank?${query}` : "/bank");
  };

  // Only to label the concept pills: an id in the URL means nothing to read.
  const { data: concepts } = useQuery({
    queryKey: keys.concepts(),
    queryFn: api.listConcepts,
    enabled: selected.concept_ids.length > 0,
  });
  const conceptTitle = (id: string) =>
    concepts?.find((concept) => concept.id === id)?.title ?? "concept";

  const query = toQuery(facets);
  const { data, isPending, isError, error } = useQuery({
    queryKey: keys.search(query),
    queryFn: () => api.searchMistakes(query),
  });

  const filtering = !isEmpty(facets);

  // A concept with nothing tagged returns an empty bank, which is correct and reads
  // exactly like a broken filter. Say which concept, and offer the way out.
  const onlyEmptyConcept =
    facets.concept_ids.length === 1 &&
    facets.urgency.length === 0 &&
    facets.section.length === 0 &&
    facets.error_type.length === 0 &&
    facets.topics.length === 0 &&
    facets.hasConcept === null &&
    !facets.text.trim();

  const emptyTitle = onlyEmptyConcept
    ? `Nothing is tagged with \u201c${conceptTitle(facets.concept_ids[0])}\u201d yet.`
    : filtering
      ? "Nothing matches all of those."
      : "Nothing here.";

  const emptyBody = onlyEmptyConcept
    ? "The concept exists \u2014 no question has been filed under it. Open it and tag some, or tag from a question\u2019s own page."
    : filtering
      ? "The filters narrow each other, so a question has to satisfy every one. Drop one and see."
      : "No question in the bank yet.";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">The bank</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Every question you have missed, filed by what went wrong. Pick as many filters
          as you like — they narrow each other.
        </p>
      </div>

      <Input
        value={facets.text}
        onChange={(event) => setText(event.target.value)}
        placeholder="Search the questions…"
        aria-label="Search the questions"
      />

      {filtering && (
        <div className="flex flex-wrap items-center gap-1.5">
          {facets.concept_ids.map((value) => (
            <Pill
              key={value}
              label={conceptTitle(value)}
              onRemove={() => apply(toggle(facets, "concept_ids", value))}
            />
          ))}
          {facets.hasConcept !== null && (
            <Pill
              label={facets.hasConcept ? "Filed under a concept" : "No concept yet"}
              onRemove={() => apply({ ...facets, hasConcept: null })}
            />
          )}
          {facets.urgency.map((value) => (
            <Pill
              key={value}
              label={<UrgencyBadge urgency={value as Urgency} />}
              onRemove={() => apply(toggle(facets, "urgency", value))}
            />
          ))}
          {facets.section.map((value) => (
            <Pill
              key={value}
              label={SECTION_LABELS[value as Section]}
              onRemove={() => apply(toggle(facets, "section", value))}
            />
          ))}
          {facets.error_type.map((value) => (
            <Pill
              key={value}
              label={ERROR_TYPE_LABELS[value as ErrorType] ?? value}
              onRemove={() => apply(toggle(facets, "error_type", value))}
            />
          ))}
          {facets.topics.map((value) => (
            <Pill
              key={value}
              label={value}
              onRemove={() => apply(toggle(facets, "topics", value))}
            />
          ))}
          <Button size="sm" variant="ghost" onClick={() => apply(NO_FACETS)}>
            Clear all
          </Button>
        </div>
      )}

      {/* One concept selected: show the concept, then the questions under it. */}
      {selected.concept_ids.length === 1 && (
        <ConceptHeader conceptId={selected.concept_ids[0]} />
      )}

      {isPending ? (
        <div className="space-y-3">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
        </div>
      ) : isError ? (
        <Unreachable error={error as Error} />
      ) : data && data.length > 0 ? (
        <>
          <p className="text-sm text-muted-foreground">
            {data.length} question{data.length === 1 ? "" : "s"}
          </p>
          <div className="space-y-3">
            {data.map((mistake) => (
              <MistakeCard key={mistake.id} mistake={mistake} />
            ))}
          </div>
        </>
      ) : (
        <Empty
          title={emptyTitle}
          body={emptyBody}
          action={
            onlyEmptyConcept
              ? { href: `/concepts/${facets.concept_ids[0]}`, label: "Tag questions with it" }
              : { href: "/log", label: "Log a miss" }
          }
        />
      )}
    </div>
  );
}

export default function BankPage() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <BankList />
    </Suspense>
  );
}
