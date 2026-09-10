"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { ConceptForm } from "@/components/app/concept-form";
import { Empty } from "@/components/app/empty";
import { PageHeader } from "@/components/app/page-header";
import { Unreachable } from "@/components/app/unreachable";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, keys } from "@/lib/api";
import { SECTION_LABELS } from "@/lib/labels";

/** Math and English are kept apart because a concept belongs to one or the other,
 *  and mixing them makes the list something to scan rather than something to open.
 *  A concept that fits neither still needs a home, so it gets its own group. */
const GROUPS = [
  { key: "math" as const, label: SECTION_LABELS.math },
  { key: "reading_writing" as const, label: SECTION_LABELS.reading_writing },
  { key: "unfiled" as const, label: "Neither section" },
];

export default function ConceptsPage() {
  const [writing, setWriting] = useState(false);
  // Every group open to begin with. A collapsed list of two things is worse than no
  // grouping, and leaving "Neither section" shut hides a concept you just wrote
  // simply because you did not pick a section for it.
  const [expanded, setExpanded] = useState<string[]>([
    "math",
    "reading_writing",
    "unfiled",
  ]);
  const { data, isPending, isError, error } = useQuery({
    queryKey: keys.concepts(),
    queryFn: api.listConcepts,
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Concepts"
        lede="The thing behind a family of misses — the rule you keep forgetting, not the question you got wrong."
        actions={
          <Button variant={writing ? "ghost" : "default"} onClick={() => setWriting(!writing)}>
            {writing ? "Cancel" : "Write a concept"}
          </Button>
        }
      />

      {writing && (
        <Card>
          <CardContent>
            <ConceptForm onDone={() => setWriting(false)} />
          </CardContent>
        </Card>
      )}

      {isPending ? (
        <div className="space-y-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : isError ? (
        <Unreachable error={error as Error} />
      ) : data && data.length > 0 ? (
        <div className="space-y-3">
          {GROUPS.map((group) => {
            const inGroup = data.filter((concept) =>
              group.key === "unfiled"
                ? concept.section === null
                : concept.section === group.key,
            );
            if (inGroup.length === 0) return null;
            const open = expanded.includes(group.key);

            return (
              <section key={group.key} className="rounded-xl border">
                <button
                  type="button"
                  aria-expanded={open}
                  onClick={() =>
                    setExpanded(
                      open
                        ? expanded.filter((value) => value !== group.key)
                        : [...expanded, group.key],
                    )
                  }
                  className="flex w-full items-center gap-2 px-4 py-3 text-left transition-colors hover:bg-muted/50"
                >
                  {/* Decoration: aria-expanded already says open or shut, and a
                      glyph in the accessible name makes the button "▾ Math". */}
                  <span aria-hidden className="text-xs text-muted-foreground">
                    {open ? "▾" : "▸"}
                  </span>
                  <span className="font-medium">{group.label}</span>
                  <span className="ml-auto text-xs text-muted-foreground">
                    {inGroup.length} concept{inGroup.length === 1 ? "" : "s"}
                  </span>
                </button>

                {open && (
                  <ul className="space-y-2 border-t px-3 py-3">
                    {inGroup.map((concept) => (
                      <li key={concept.id}>
                        <Link
                          href={`/concepts/${concept.id}`}
                          className="block rounded-lg border px-4 py-3 transition-colors hover:border-foreground/20 hover:bg-muted/30"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="font-medium">{concept.title}</h3>
                            <span className="ml-auto text-xs text-muted-foreground">
                              {concept.question_count} question
                              {concept.question_count === 1 ? "" : "s"}
                            </span>
                          </div>
                          {concept.body && (
                            <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                              {concept.body}
                            </p>
                          )}
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            );
          })}
        </div>
      ) : (
        !writing && (
          <Empty
            title="No concepts yet."
            body="A concept is the thing behind a family of misses — the rule you keep forgetting, not the question you got wrong. Write the first one."
            onAction={{ label: "Write your first concept", onClick: () => setWriting(true) }}
          />
        )
      )}
    </div>
  );
}
