"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Empty } from "@/components/app/empty";
import { MistakeCard } from "@/components/app/mistake-card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api, keys, type MistakeFilters } from "@/lib/api";
import { ERROR_TYPE_LABELS, SECTION_LABELS } from "@/lib/labels";
import type { ErrorType, Section } from "@/lib/types";
import { cn } from "@/lib/utils";

function Chip({
  href,
  active,
  children,
}: {
  href: string;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "rounded-full border px-3 py-1 text-xs transition-colors",
        active ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted",
      )}
    >
      {children}
    </Link>
  );
}

function BankList() {
  const params = useSearchParams();
  const [search, setSearch] = useState("");

  const errorType = (params.get("error_type") as ErrorType | null) ?? undefined;
  const section = (params.get("section") as Section | null) ?? undefined;
  const topic = params.get("topic") ?? undefined;

  const filters: MistakeFilters = {
    error_type: errorType,
    section,
    topic,
    q: search.trim() || undefined,
  };

  const { data, isPending } = useQuery({
    queryKey: keys.mistakes(filters),
    queryFn: () => api.listMistakes(filters),
  });

  const stats = useQuery({ queryKey: keys.stats(), queryFn: api.stats });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">The bank</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Every question you have missed, filed by what went wrong.
        </p>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <Chip href="/bank" active={!errorType && !section && !topic}>
          Everything
        </Chip>
        {(Object.keys(SECTION_LABELS) as Section[]).map((value) => (
          <Chip key={value} href={`/bank?section=${value}`} active={section === value}>
            {SECTION_LABELS[value]}
          </Chip>
        ))}
        {stats.data?.by_error_type.map((slot) => (
          <Chip
            key={slot.key}
            href={`/bank?error_type=${slot.key}`}
            active={errorType === slot.key}
          >
            {ERROR_TYPE_LABELS[slot.key as ErrorType] ?? slot.key} · {slot.count}
          </Chip>
        ))}
      </div>

      <Input
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder="Search the questions…"
        aria-label="Search the questions"
      />

      {isPending ? (
        <div className="space-y-3">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
        </div>
      ) : data && data.length > 0 ? (
        <div className="space-y-3">
          {data.map((mistake) => (
            <MistakeCard key={mistake.id} mistake={mistake} />
          ))}
        </div>
      ) : (
        <Empty
          title="Nothing here."
          body="No question in the bank matches this filter yet."
          action={{ href: "/log", label: "Log a miss" }}
        />
      )}
    </div>
  );
}

export default function BankPage() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <BankList />
    </Suspense>
  );
}
