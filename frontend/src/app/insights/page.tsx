"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Empty } from "@/components/app/empty";
import { InsightView } from "@/components/app/insight-view";
import { PageHeader } from "@/components/app/page-header";
import { Panel } from "@/components/app/panel";
import { Section } from "@/components/app/section";
import { Unreachable } from "@/components/app/unreachable";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { api, keys } from "@/lib/api";
import { cn } from "@/lib/utils";

/** A whole-bank reading of what you have been doing right and wrong, kept so
 *  this month's can be set beside last month's. */
export default function InsightsPage() {
  const queryClient = useQueryClient();
  const [focus, setFocus] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  const insights = useQuery({ queryKey: keys.insights(), queryFn: api.listInsights });
  // For the links under each point: a question's own words beat "Question 3".
  const mistakes = useQuery({ queryKey: keys.mistakes(), queryFn: () => api.listMistakes() });
  const questionText = useMemo(
    () => new Map((mistakes.data ?? []).map((m) => [m.id, m.question_text])),
    [mistakes.data],
  );

  const write = useMutation({
    mutationFn: () => api.newInsight(focus.trim() || null),
    onSuccess: (made) => {
      queryClient.setQueryData(keys.insights(), (current: typeof insights.data) => [
        made,
        ...(current ?? []),
      ]);
      setSelected(made.id);
      setFocus("");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteInsight(id),
    onSuccess: (_, id) => {
      queryClient.setQueryData(keys.insights(), (current: typeof insights.data) =>
        (current ?? []).filter((insight) => insight.id !== id),
      );
      setSelected(null);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const list = insights.data ?? [];
  const shown = list.find((insight) => insight.id === selected) ?? list[0];

  return (
    <div className="space-y-6">
      <PageHeader title="Insights" />

      <Panel className="px-6 py-5">
        <form
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (!write.isPending) write.mutate();
          }}
        >
          <p className="text-sm text-muted-foreground">
            Reads every recent question — the debrief, what you said happened, what you
            told the debrief, and how your reviews went — and says what you have been
            doing right and wrong.
          </p>
          <Textarea
            rows={2}
            value={focus}
            onChange={(event) => setFocus(event.target.value)}
            placeholder="Anything in particular? e.g. Why do I keep losing points on grammar?"
            aria-label="What to look at"
          />
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={write.isPending}>
              {write.isPending ? "Reading your bank…" : "Analyse my bank"}
            </Button>
            {write.isPending && (
              <span className="text-xs text-muted-foreground" role="status">
                This can take a minute.
              </span>
            )}
          </div>
        </form>
      </Panel>

      {insights.isPending ? (
        <Skeleton className="h-64 w-full" />
      ) : insights.isError ? (
        <Unreachable error={insights.error as Error} />
      ) : !shown ? (
        <Empty
          title="No analysis yet."
          body="Run one above. Each is kept here, so you can come back to it and compare."
        />
      ) : (
        <div className="grid gap-6 md:grid-cols-[1fr_14rem]">
          <InsightView insight={shown} questionText={questionText} />

          <Section title="Earlier analyses">
            <ul className="space-y-1">
              {list.map((insight) => (
                <li key={insight.id}>
                  <button
                    type="button"
                    onClick={() => setSelected(insight.id)}
                    aria-current={insight.id === shown.id ? "true" : undefined}
                    className={cn(
                      "w-full rounded-md px-3 py-2 text-left text-sm transition-colors",
                      insight.id === shown.id
                        ? "bg-accent text-accent-foreground"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    <span className="block">
                      {format(new Date(insight.created_at), "d MMM yyyy, HH:mm")}
                    </span>
                    {insight.focus && (
                      <span className="line-clamp-1 text-xs opacity-80">{insight.focus}</span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
            <Button
              variant="ghost"
              size="sm"
              className="text-muted-foreground"
              disabled={remove.isPending}
              onClick={() => remove.mutate(shown.id)}
            >
              Delete this analysis
            </Button>
          </Section>
        </div>
      )}
    </div>
  );
}
