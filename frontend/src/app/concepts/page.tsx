"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { ConceptForm } from "@/components/app/concept-form";
import { Empty } from "@/components/app/empty";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, keys } from "@/lib/api";
import { SECTION_LABELS } from "@/lib/labels";

export default function ConceptsPage() {
  const [writing, setWriting] = useState(false);
  const { data, isPending } = useQuery({
    queryKey: keys.concepts(),
    queryFn: api.listConcepts,
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Concepts</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            The things worth knowing. Write one down, then tag the questions that keep
            catching you on it.
          </p>
        </div>
        <Button variant={writing ? "ghost" : "default"} onClick={() => setWriting(!writing)}>
          {writing ? "Cancel" : "Write a concept"}
        </Button>
      </div>

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
      ) : data && data.length > 0 ? (
        <div className="space-y-3">
          {data.map((concept) => (
            <Link key={concept.id} href={`/concepts/${concept.id}`} className="block">
              <Card className="transition-colors hover:border-foreground/20">
                <CardContent className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-medium">{concept.title}</h2>
                    {concept.section && (
                      <Badge variant="outline">{SECTION_LABELS[concept.section]}</Badge>
                    )}
                    <span className="ml-auto text-xs text-muted-foreground">
                      {concept.question_count} question
                      {concept.question_count === 1 ? "" : "s"}
                    </span>
                  </div>
                  {concept.body && (
                    <p className="line-clamp-2 text-sm text-muted-foreground">
                      {concept.body}
                    </p>
                  )}
                </CardContent>
              </Card>
            </Link>
          ))}
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
