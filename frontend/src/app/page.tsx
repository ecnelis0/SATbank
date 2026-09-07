"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Empty } from "@/components/app/empty";
import { MistakeCard } from "@/components/app/mistake-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, keys } from "@/lib/api";
import { ERROR_TYPE_LABELS } from "@/lib/labels";
import type { ErrorType } from "@/lib/types";

function Stat({ value, label }: { value: number | string; label: string }) {
  return (
    <Card>
      <CardContent>
        <p className="text-3xl font-semibold tabular-nums">{value}</p>
        <p className="mt-1 text-sm text-muted-foreground">{label}</p>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const stats = useQuery({ queryKey: keys.stats(), queryFn: api.stats });
  const recent = useQuery({
    queryKey: keys.mistakes(),
    queryFn: () => api.listMistakes(),
  });

  if (stats.isPending) {
    return <Skeleton className="h-64 w-full" />;
  }

  if (stats.isError) {
    return (
      <Empty
        title="Can't reach the API."
        body={`${(stats.error as Error).message}. Start the backend with \`uv run uvicorn app.main:app --reload\` in backend/.`}
      />
    );
  }

  const data = stats.data;
  const slots = data.by_error_type;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Your mistakes</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Every miss comes back at 1 hour, 24 hours, 72 hours, 1 week and 1 month.
          </p>
        </div>
        <div className="flex gap-2">
          <Button render={<Link href="/log" />} nativeButton={false} variant="secondary">
            Log a miss
          </Button>
          {data.due_now > 0 && (
            <Button render={<Link href="/review" />} nativeButton={false}>
              Review {data.due_now}
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <Stat value={data.total_mistakes} label="questions in the bank" />
        <Stat value={data.due_now} label="due for review now" />
        <Stat value={data.reviews_completed} label="reviews answered" />
      </div>

      {data.total_mistakes === 0 ? (
        <Empty
          title="The bank is empty."
          body="Log the first question you got wrong. The analysis and the review schedule follow automatically."
          action={{ href: "/log", label: "Log a miss" }}
        />
      ) : (
        <>
          <section>
            <h2 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
              Why you&rsquo;re losing points
            </h2>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {slots.map((slot) => (
                <Link
                  key={slot.key}
                  href={`/bank?error_type=${slot.key}`}
                  className="flex items-center justify-between rounded-lg border px-4 py-3 transition-colors hover:bg-muted/50"
                >
                  <span className="text-sm">
                    {ERROR_TYPE_LABELS[slot.key as ErrorType] ?? slot.key}
                  </span>
                  <span className="text-sm font-medium tabular-nums">{slot.count}</span>
                </Link>
              ))}
              {slots.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No analyses have landed yet.
                </p>
              )}
            </div>
          </section>

          <section>
            <h2 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
              Latest
            </h2>
            <div className="mt-3 space-y-3">
              {recent.data?.slice(0, 5).map((mistake) => (
                <MistakeCard key={mistake.id} mistake={mistake} />
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
