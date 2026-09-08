"use client";

import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { API_URL } from "@/lib/api";

/** Shown when a load failed, in place of an empty state.
 *
 *  The distinction matters more here than almost anywhere: "we could not reach the
 *  API" and "you have no questions" look identical if you render the empty state for
 *  both, and in an app whose whole promise is not losing your work, the second
 *  message is alarming and false. */
export function Unreachable({ error }: { error?: Error | null }) {
  const queryClient = useQueryClient();

  return (
    <div
      role="alert"
      className="rounded-xl border border-destructive/40 bg-destructive/5 px-6 py-10 text-center"
    >
      <p className="font-medium">Can&rsquo;t reach the app&rsquo;s API.</p>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
        Nothing has been lost — your questions are on disk. The API just isn&rsquo;t
        answering at <code className="font-mono">{API_URL}</code>. Start it with{" "}
        <code className="font-mono">uv run uvicorn app.main:app --reload</code> in{" "}
        <code className="font-mono">backend/</code>.
      </p>
      {error?.message && (
        <p className="mt-2 font-mono text-xs text-muted-foreground">{error.message}</p>
      )}
      <Button className="mt-5" onClick={() => queryClient.invalidateQueries()}>
        Try again
      </Button>
    </div>
  );
}
