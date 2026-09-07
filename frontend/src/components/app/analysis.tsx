"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, keys } from "@/lib/api";
import { ERROR_TYPE_BLURBS, ERROR_TYPE_LABELS } from "@/lib/labels";
import type { Mistake } from "@/lib/types";

function Section({ title, body }: { title: string; body: string }) {
  return (
    <div>
      <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {title}
      </h3>
      <p className="mt-1 text-sm leading-relaxed whitespace-pre-line">{body}</p>
    </div>
  );
}

export function AnalysisPanel({ mistake }: { mistake: Mistake }) {
  const queryClient = useQueryClient();
  const retry = useMutation({
    mutationFn: () => api.reanalyze(mistake.id),
    onSuccess: (updated) => {
      queryClient.setQueryData(keys.mistake(mistake.id), updated);
      queryClient.invalidateQueries({ queryKey: keys.stats() });
      toast[updated.analysis_status === "ready" ? "success" : "error"](
        updated.analysis_status === "ready" ? "Analysed." : "Still failing.",
      );
    },
    onError: (error: Error) => toast.error(error.message),
  });

  if (mistake.analysis_status === "pending") {
    return (
      <div className="space-y-3" aria-live="polite" aria-busy="true">
        <p className="text-sm text-muted-foreground">Analysing this miss…</p>
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-2/3" />
      </div>
    );
  }

  if (mistake.analysis_status === "failed") {
    return (
      <div className="space-y-3">
        <p className="text-sm">
          The analysis did not come back. The question is still logged and still on the
          review ladder.
        </p>
        {mistake.analysis_error && (
          <p className="font-mono text-xs text-muted-foreground">{mistake.analysis_error}</p>
        )}
        <Button size="sm" onClick={() => retry.mutate()} disabled={retry.isPending}>
          {retry.isPending ? "Trying again…" : "Try again"}
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        {mistake.error_type && (
          <Badge variant="secondary">{ERROR_TYPE_LABELS[mistake.error_type]}</Badge>
        )}
        {mistake.topic && <Badge variant="outline">{mistake.topic}</Badge>}
        {mistake.difficulty && <Badge variant="outline">{mistake.difficulty}</Badge>}
      </div>

      {mistake.error_type && (
        <p className="text-sm text-muted-foreground">
          {ERROR_TYPE_BLURBS[mistake.error_type]}
        </p>
      )}

      {mistake.why_wrong && <Section title="Why you got it wrong" body={mistake.why_wrong} />}
      {mistake.trap && <Section title="The trap" body={mistake.trap} />}
      {mistake.correct_reasoning && (
        <Section title="How it works" body={mistake.correct_reasoning} />
      )}

      {mistake.takeaway && (
        <div className="rounded-lg border-l-2 border-primary bg-muted/50 px-4 py-3">
          <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Remember
          </h3>
          <p className="mt-1 text-sm font-medium">{mistake.takeaway}</p>
        </div>
      )}

      {mistake.analyzed_by && (
        <p className="text-xs text-muted-foreground">Analysis by {mistake.analyzed_by}.</p>
      )}
    </div>
  );
}
