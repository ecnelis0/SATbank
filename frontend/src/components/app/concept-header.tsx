"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Gallery } from "@/components/app/gallery";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, keys } from "@/lib/api";
import { SECTION_LABELS } from "@/lib/labels";

/** The concept itself, shown above its questions.
 *
 *  Filtering the bank by a concept used to show only the questions, which meant the
 *  thing you were actually revising - the rule, in your own words, with its diagram -
 *  was the one part you could not see. */
export function ConceptHeader({ conceptId }: { conceptId: string }) {
  const { data: concept, isPending } = useQuery({
    queryKey: keys.concept(conceptId),
    queryFn: () => api.getConcept(conceptId),
  });

  if (isPending) return <Skeleton className="h-28 w-full" />;
  if (!concept) return null;

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold tracking-tight">{concept.title}</h2>
            {concept.section && (
              <Badge variant="outline">{SECTION_LABELS[concept.section]}</Badge>
            )}
          </div>
          <Link
            href={`/concepts/${concept.id}`}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            Open concept →
          </Link>
        </div>

        {concept.body && (
          <p className="text-sm leading-relaxed whitespace-pre-line">{concept.body}</p>
        )}

        {concept.images.length > 0 && (
          <Gallery
            images={concept.images}
            title="Diagrams"
            noun="Diagram"
            context="of the concept"
          />
        )}

        <p className="text-xs text-muted-foreground">
          {concept.question_count} question{concept.question_count === 1 ? "" : "s"} filed
          under this concept.
        </p>
      </CardContent>
    </Card>
  );
}
