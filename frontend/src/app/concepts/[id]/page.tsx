"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { ConceptForm } from "@/components/app/concept-form";
import { Empty } from "@/components/app/empty";
import { MistakeCard } from "@/components/app/mistake-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, keys } from "@/lib/api";
import { SECTION_LABELS } from "@/lib/labels";

export default function ConceptPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);

  const { data: concept, isPending, isError } = useQuery({
    queryKey: keys.concept(id),
    queryFn: () => api.getConcept(id),
  });

  const untag = useMutation({
    mutationFn: (mistakeId: string) => api.untagQuestion(id, mistakeId),
    onSuccess: (updated) => {
      queryClient.setQueryData(keys.concept(id), updated);
      queryClient.invalidateQueries({ queryKey: ["mistakes"] });
      queryClient.invalidateQueries({ queryKey: keys.concepts() });
      queryClient.invalidateQueries({ queryKey: keys.stats() });
      toast.success("Untagged.");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const remove = useMutation({
    mutationFn: () => api.deleteConcept(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.concepts() });
      queryClient.invalidateQueries({ queryKey: ["mistakes"] });
      queryClient.invalidateQueries({ queryKey: keys.stats() });
      toast.success("Concept deleted. The questions are untouched.");
      router.push("/concepts");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  if (isPending) return <Skeleton className="h-96 w-full" />;
  if (isError || !concept) {
    return (
      <Empty
        title="No such concept."
        body="It was deleted, or it belongs to someone else."
        action={{ href: "/concepts", label: "Back to concepts" }}
      />
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Link href="/concepts" className="text-sm text-muted-foreground hover:text-foreground">
        ← Concepts
      </Link>

      <Card>
        <CardContent>
          {editing ? (
            <ConceptForm concept={concept} onDone={() => setEditing(false)} />
          ) : (
            <div className="space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <h1 className="text-xl font-semibold tracking-tight">{concept.title}</h1>
                <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
                  Edit
                </Button>
              </div>
              {concept.section && (
                <Badge variant="outline">{SECTION_LABELS[concept.section]}</Badge>
              )}
              {concept.body ? (
                <p className="text-sm leading-relaxed whitespace-pre-line">{concept.body}</p>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No notes yet. Edit to write what this actually means.
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
            Questions under this concept
          </h2>
          {concept.mistakes.length > 0 && (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => router.push(`/bank?concept=${concept.id}`)}
            >
              Filter the bank
            </Button>
          )}
        </div>

        {concept.mistakes.length === 0 ? (
          <div className="rounded-xl border border-dashed px-6 py-10 text-center">
            <p className="text-sm font-medium">Nothing tagged yet.</p>
            <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
              Open a question in the bank and tag it with this concept — the tag lives on
              the question page.
            </p>
            <Button className="mt-4" onClick={() => router.push("/bank")}>
              Go to the bank
            </Button>
          </div>
        ) : (
          concept.mistakes.map((mistake) => (
            <div key={mistake.id} className="space-y-1">
              <MistakeCard mistake={mistake} />
              <div className="flex justify-end">
                <Button
                  size="xs"
                  variant="ghost"
                  className="text-muted-foreground"
                  disabled={untag.isPending}
                  onClick={() => untag.mutate(mistake.id)}
                >
                  Untag
                </Button>
              </div>
            </div>
          ))
        )}
      </section>

      <Button
        variant="ghost"
        className="text-muted-foreground"
        disabled={remove.isPending}
        onClick={() => {
          if (window.confirm("Delete this concept? The questions themselves stay.")) {
            remove.mutate();
          }
        }}
      >
        Delete this concept
      </Button>
    </div>
  );
}
