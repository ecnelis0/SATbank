"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";

import { AnalysisPanel } from "@/components/app/analysis";
import { ConceptTags } from "@/components/app/concept-tags";
import { MistakeImages } from "@/components/app/images";
import { MistakeLabels } from "@/components/app/mistake-labels";
import { Empty } from "@/components/app/empty";
import { Ladder } from "@/components/app/ladder";
import { QuestionCard } from "@/components/app/question-card";
import { Panel, SPINE } from "@/components/app/panel";
import { Section } from "@/components/app/section";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
      <div className="flex flex-wrap items-center gap-2">
        <Link href="/bank" className="text-sm text-muted-foreground hover:text-foreground">
          ← The bank
        </Link>
        {/* No urgency badge here: the debrief already carries one, and the same
            badge twice on one screen is a duplicate to read and to announce. The
            coloured spine on the question panel says it at a glance. */}
        <Badge variant="outline" className="ml-auto">
          {SECTION_LABELS[mistake.section]}
        </Badge>
      </div>

      <Panel
        spine={mistake.urgency ? SPINE[mistake.urgency] : undefined}
        className="px-6 py-5"
      >
        <QuestionCard mistake={mistake} />
      </Panel>

      <Section title="The debrief">
        <Panel className="px-6 py-5">
          <AnalysisPanel mistake={mistake} editable />
        </Panel>
      </Section>

      <Panel className="px-6 py-5">
        <MistakeImages mistake={mistake} editable />
      </Panel>

      <Panel className="px-6 py-5">
        <MistakeLabels mistake={mistake} editable />
      </Panel>

      <Panel className="px-6 py-5">
        <ConceptTags mistake={mistake} />
      </Panel>

      <Section
        title="Review schedule"
        description={`Logged ${format(new Date(mistake.created_at), "d MMM yyyy, HH:mm")}.`}
      >
        <Panel className="px-6 py-5">
          <Ladder reviews={mistake.reviews} />
        </Panel>
      </Section>

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
