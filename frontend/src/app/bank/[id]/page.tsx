"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";

import { AnalysisPanel } from "@/components/app/analysis";
import { Empty } from "@/components/app/empty";
import { Ladder } from "@/components/app/ladder";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { api, keys } from "@/lib/api";
import { SECTION_LABELS } from "@/lib/labels";

export default function MistakePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: mistake, isPending, isError } = useQuery({
    queryKey: keys.mistake(id),
    queryFn: () => api.getMistake(id),
    // The analysis arrives moments after logging; stop polling once it lands.
    refetchInterval: (query) =>
      query.state.data?.analysis_status === "pending" ? 1500 : false,
  });

  const remove = useMutation({
    mutationFn: () => api.deleteMistake(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mistakes"] });
      queryClient.invalidateQueries({ queryKey: keys.stats() });
      queryClient.invalidateQueries({ queryKey: ["reviews"] });
      toast.success("Removed from the bank.");
      router.push("/bank");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  if (isPending) return <Skeleton className="h-96 w-full" />;
  if (isError || !mistake) {
    return (
      <Empty
        title="Not in your bank."
        body="This question either never existed or belongs to someone else."
        action={{ href: "/bank", label: "Back to the bank" }}
      />
    );
  }

  return (
    <article className="mx-auto max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <Link href="/bank" className="text-sm text-muted-foreground hover:text-foreground">
          ← The bank
        </Link>
        <Badge variant="outline">{SECTION_LABELS[mistake.section]}</Badge>
      </div>

      <Card>
        <CardContent className="space-y-4">
          {mistake.source && (
            <p className="text-xs text-muted-foreground">{mistake.source}</p>
          )}
          <p className="leading-relaxed whitespace-pre-line">{mistake.question_text}</p>

          {mistake.choices && (
            <ol className="space-y-1.5 text-sm text-muted-foreground">
              {mistake.choices.map((choice, index) => (
                <li key={choice}>
                  <span className="font-mono">{String.fromCharCode(65 + index)}.</span>{" "}
                  {choice}
                </li>
              ))}
            </ol>
          )}

          <Separator />

          <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
            <span>
              <span className="text-muted-foreground">You put </span>
              <span className="font-medium text-destructive">{mistake.your_answer}</span>
            </span>
            <span>
              <span className="text-muted-foreground">Answer </span>
              <span className="font-medium">{mistake.correct_answer}</span>
            </span>
          </div>

          {mistake.student_note && (
            <p className="text-sm text-muted-foreground italic">
              Your note: {mistake.student_note}
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <AnalysisPanel mistake={mistake} />
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-4">
          <h2 className="text-sm font-medium">Review schedule</h2>
          <Ladder reviews={mistake.reviews} />
          <p className="text-xs text-muted-foreground">
            Logged {format(new Date(mistake.created_at), "d MMM yyyy, HH:mm")}.
          </p>
        </CardContent>
      </Card>

      <Button
        variant="ghost"
        className="text-muted-foreground"
        onClick={() => remove.mutate()}
        disabled={remove.isPending}
      >
        Remove from the bank
      </Button>
    </article>
  );
}
