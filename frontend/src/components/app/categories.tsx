"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { UrgencyBadge } from "@/components/app/urgency-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { api, keys } from "@/lib/api";
import { ERROR_TYPE_LABELS, SECTION_LABELS } from "@/lib/labels";
import { URGENCIES, type ErrorType, type Section } from "@/lib/types";

function Row({ href, label, count }: { href: string; label: React.ReactNode; count: number }) {
  return (
    <Link
      href={href}
      className="flex items-center justify-between gap-3 rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-muted"
    >
      <span className="truncate">{label}</span>
      <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{count}</span>
    </Link>
  );
}

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-1 px-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {title}
      </h3>
      <div className="space-y-0.5">{children}</div>
    </section>
  );
}

/** Everything in the bank, grouped, with live counts. The browsing half of the rail. */
export function Categories() {
  const { data, isPending } = useQuery({ queryKey: keys.stats(), queryFn: api.stats });

  if (isPending) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-5 w-full" />
        <Skeleton className="h-5 w-full" />
        <Skeleton className="h-5 w-2/3" />
      </div>
    );
  }

  if (!data) return null;

  const countOf = (slots: { key: string; count: number }[], key: string) =>
    slots.find((slot) => slot.key === key)?.count ?? 0;

  return (
    <div className="space-y-5">
      <Group title="How urgent">
        {URGENCIES.map((urgency) => (
          <Row
            key={urgency}
            href={`/bank?urgency=${urgency}`}
            label={<UrgencyBadge urgency={urgency} />}
            count={countOf(data.by_urgency, urgency)}
          />
        ))}
      </Group>

      <Group title="Section">
        {(Object.keys(SECTION_LABELS) as Section[]).map((section) => (
          <Row
            key={section}
            href={`/bank?section=${section}`}
            label={SECTION_LABELS[section]}
            count={countOf(data.by_section, section)}
          />
        ))}
      </Group>

      {data.by_error_type.length > 0 && (
        <Group title="Why you missed it">
          {data.by_error_type.map((slot) => (
            <Row
              key={slot.key}
              href={`/bank?error_type=${slot.key}`}
              label={ERROR_TYPE_LABELS[slot.key as ErrorType] ?? slot.key}
              count={slot.count}
            />
          ))}
        </Group>
      )}

      {data.by_topic.length > 0 && (
        <Group title="Topic">
          {data.by_topic.map((slot) => (
            <Row
              key={slot.key}
              href={`/bank?topic=${encodeURIComponent(slot.key)}`}
              label={slot.key}
              count={slot.count}
            />
          ))}
        </Group>
      )}
    </div>
  );
}
