"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";

import { Empty } from "@/components/app/empty";
import { MistakeCard } from "@/components/app/mistake-card";
import { PageHeader } from "@/components/app/page-header";
import { Panel } from "@/components/app/panel";
import { Section } from "@/components/app/section";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, keys } from "@/lib/api";
import type { VideoConcept } from "@/lib/types";

/** 125 → "2:05". The stamp is the point: it is what turns a summary into
 *  something you can study against the video. */
function stamp(seconds: number | null) {
  if (seconds === null) return null;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function ConceptRow({ concept }: { concept: VideoConcept }) {
  return (
    <Panel className="px-5 py-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-medium">
          <Link href={`/concepts/${concept.id}`} className="hover:underline">
            {concept.title}
          </Link>
        </h3>
        <div className="flex items-center gap-3 text-xs">
          {concept.question_count > 0 && (
            <span className="text-muted-foreground">
              {concept.question_count} question{concept.question_count === 1 ? "" : "s"}
            </span>
          )}
          {concept.watch_url && concept.start_seconds !== null && (
            <a
              href={concept.watch_url}
              target="_blank"
              rel="noreferrer"
              className="rounded-full border border-azurite-deep/25 bg-azurite/10 px-2 py-0.5 font-mono text-azurite-deep hover:bg-azurite/20"
            >
              ▶ {stamp(concept.start_seconds)}
            </a>
          )}
        </div>
      </div>
      {concept.body && (
        <p className="mt-2 text-sm leading-relaxed whitespace-pre-wrap">{concept.body}</p>
      )}
    </Panel>
  );
}

export default function VideoPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();

  const video = useQuery({
    queryKey: keys.video(id),
    queryFn: () => api.getVideo(id),
    refetchInterval: (query) => (query.state.data?.status === "pending" ? 3000 : false),
  });

  const reread = useMutation({
    mutationFn: () => api.rereadVideo(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.video(id) });
      toast.success("Reading it again.");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const remove = useMutation({
    mutationFn: () => api.deleteVideo(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["videos"] });
      toast.success("Deleted. Concepts you had tagged questions onto were kept.");
      router.push("/videos");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  if (video.isPending) return <Skeleton className="h-64 w-full" />;
  if (video.isError) {
    return <Empty title="Can't reach the app's API." body={(video.error as Error).message} />;
  }

  const data = video.data;

  return (
    <div className="space-y-8">
      <PageHeader
        title={data.title ?? "Video"}
        actions={
          <>
            <a
              href={data.url}
              target="_blank"
              rel="noreferrer"
              className="rounded-md border px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground"
            >
              Watch on YouTube
            </a>
            <Button
              variant="secondary"
              size="sm"
              disabled={reread.isPending || data.status === "pending"}
              onClick={() => reread.mutate()}
            >
              {reread.isPending ? "Asking…" : "Read it again"}
            </Button>
          </>
        }
      />

      <p className="text-sm text-muted-foreground">
        {[data.author, data.subject && `filed under ${data.subject}`]
          .filter(Boolean)
          .join(" · ")}
      </p>

      {data.status === "pending" && (
        <Panel className="px-6 py-5">
          <p role="status" className="text-sm text-ochre">
            Reading the video. The concepts appear here when it is done.
          </p>
        </Panel>
      )}

      {data.status === "failed" && (
        <Panel className="px-6 py-5" spine="bg-seal">
          <p className="text-sm text-seal">{data.error}</p>
          {!data.has_transcript && (
            <p className="mt-2 text-xs text-muted-foreground">
              If it has no captions, paste the transcript when you add it and it will be
              read from that instead.
            </p>
          )}
        </Panel>
      )}

      {data.summary && (
        <Section title="What this covers">
          <Panel className="px-6 py-5">
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{data.summary}</p>
            {data.directions && (
              <p className="mt-3 border-t pt-3 text-xs text-muted-foreground">
                Your directions: {data.directions}
              </p>
            )}
          </Panel>
        </Section>
      )}

      {data.concepts.length > 0 && (
        <Section
          title="Concepts"
          description="Each one is a note you can revise from, and file your own missed questions under."
        >
          <div className="space-y-3">
            {data.concepts.map((concept) => (
              <ConceptRow key={concept.id} concept={concept} />
            ))}
          </div>
        </Section>
      )}

      <Section
        title="Your questions on this"
        description="Everything filed under any concept from this video."
      >
        {data.mistakes.length === 0 ? (
          <Empty
            title="Nothing tagged yet."
            body="Open a concept above and tag the questions it explains, or tag from a question's own page."
          />
        ) : (
          <div className="space-y-3">
            {data.mistakes.map((mistake) => (
              <MistakeCard key={mistake.id} mistake={mistake} />
            ))}
          </div>
        )}
      </Section>

      <Button
        variant="ghost"
        className="text-muted-foreground"
        disabled={remove.isPending}
        onClick={() => {
          if (window.confirm("Delete this video? Concepts with questions tagged on them are kept."))
            remove.mutate();
        }}
      >
        Delete this video
      </Button>
    </div>
  );
}
