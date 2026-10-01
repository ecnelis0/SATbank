"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Empty } from "@/components/app/empty";
import { PageHeader } from "@/components/app/page-header";
import { Panel } from "@/components/app/panel";
import { Section } from "@/components/app/section";
import { VideoForm } from "@/components/app/video-form";
import { Skeleton } from "@/components/ui/skeleton";
import { api, keys } from "@/lib/api";
import type { Video } from "@/lib/types";
import { cn } from "@/lib/utils";

function minutes(seconds: number | null) {
  if (!seconds) return null;
  return `${Math.round(seconds / 60)} min`;
}

/** Pending, failed and ready look different enough that the state is never a
 *  guess — a video silently doing nothing is the thing worth being loud about. */
function Status({ video }: { video: Video }) {
  if (video.status === "pending") {
    return (
      <span className="text-xs text-ochre" role="status">
        Reading it…
      </span>
    );
  }
  if (video.status === "failed") {
    return <span className="text-xs text-seal">{video.error ?? "Could not be read"}</span>;
  }
  return (
    <span className="text-xs text-muted-foreground">
      {video.concept_count} concept{video.concept_count === 1 ? "" : "s"}
    </span>
  );
}

function VideoRow({ video }: { video: Video }) {
  return (
    <Panel interactive className="px-5 py-4">
      <Link href={`/videos/${video.id}`} className="block">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h3 className="font-medium">{video.title ?? video.url}</h3>
          {video.subject && (
            <span className="rounded-full border border-malachite-deep/25 bg-malachite/10 px-2 py-0.5 text-[11px] text-malachite-deep">
              {video.subject}
            </span>
          )}
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          {[video.author, minutes(video.duration_seconds)].filter(Boolean).join(" · ")}
        </p>
        {video.summary && (
          <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">{video.summary}</p>
        )}
        <div className="mt-2">
          <Status video={video} />
        </div>
      </Link>
    </Panel>
  );
}

export default function VideosPage() {
  const [tab, setTab] = useState<string | null>(null);

  const subjects = useQuery({ queryKey: keys.videoSubjects(), queryFn: api.videoSubjects });
  const videos = useQuery({
    queryKey: keys.videos(tab),
    queryFn: () => api.listVideos(tab),
    // A video is read in the background, so the list has to notice when it lands.
    refetchInterval: (query) =>
      (query.state.data ?? []).some((video) => video.status === "pending") ? 3000 : false,
  });

  const tabs = subjects.data ?? [];

  return (
    <div className="space-y-8">
      <PageHeader title="Videos" />

      <Section
        title="Add a video"
        description="Paste a YouTube link. It comes back as concepts you can revise from, and tag your own questions onto."
      >
        <Panel className="px-6 py-5">
          <VideoForm defaultSubject={tab} />
        </Panel>
      </Section>

      {tabs.length > 0 && (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setTab(null)}
            className={cn(
              "rounded-full border px-3 py-1 text-sm transition-colors",
              tab === null
                ? "border-transparent bg-accent text-accent-foreground"
                : "border-border text-muted-foreground hover:text-foreground",
            )}
          >
            Everything
          </button>
          {tabs.map((entry) => (
            <button
              key={entry.subject ?? "unfiled"}
              type="button"
              onClick={() => setTab(entry.subject)}
              className={cn(
                "rounded-full border px-3 py-1 text-sm transition-colors",
                tab === entry.subject
                  ? "border-transparent bg-accent text-accent-foreground"
                  : "border-border text-muted-foreground hover:text-foreground",
              )}
            >
              {entry.subject ?? "No tab"}
              <span className="ml-1.5 text-xs opacity-70">{entry.video_count}</span>
            </button>
          ))}
        </div>
      )}

      {videos.isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : videos.isError ? (
        <Empty title="Can't reach the app's API." body={(videos.error as Error).message} />
      ) : (videos.data ?? []).length === 0 ? (
        <Empty
          title={tab ? `Nothing under ${tab} yet.` : "No videos yet."}
          body="Add one above. The concepts it teaches become notes you can file your own missed questions under."
        />
      ) : (
        <div className="space-y-3">
          {(videos.data ?? []).map((video) => (
            <VideoRow key={video.id} video={video} />
          ))}
        </div>
      )}
    </div>
  );
}
