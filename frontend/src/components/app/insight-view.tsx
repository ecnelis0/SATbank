"use client";

import { format } from "date-fns";
import Link from "next/link";

import { Panel } from "@/components/app/panel";
import { Section } from "@/components/app/section";
import type { CoachPoint, Insight } from "@/lib/types";

const ANALYZER_LABELS: Record<string, string> = {
  agent: "Claude",
  claude: "Claude API",
  openai: "OpenAI",
  stub: "the offline reader",
};

/** One whole-bank analysis. The counts beside the prose were made by the
 *  database, so they are shown as numbers the model was given, not as its claims. */
export function InsightView({
  insight,
  questionText,
}: {
  insight: Insight;
  /** Question id → its text, for the links under each point. */
  questionText: Map<string, string>;
}) {
  const { report, stats } = insight;

  return (
    <article className="space-y-6" aria-label="Analysis">
      {insight.focus && (
        <Panel className="px-6 py-5">
          <p className="text-xs text-muted-foreground">You asked</p>
          <p className="mt-1 font-medium">{insight.focus}</p>
          {report.answer && (
            <p className="mt-3 text-sm leading-relaxed whitespace-pre-wrap">{report.answer}</p>
          )}
        </Panel>
      )}

      <Panel className="px-6 py-5">
        <p className="text-sm leading-relaxed whitespace-pre-wrap">{report.overview}</p>
        <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Questions read" value={stats.questions} />
          <Stat label="Right on review" value={stats.reviews_right} />
          <Stat label="Still wrong on review" value={stats.reviews_wrong} />
          <Stat label="Talked to the debrief" value={stats.talked_to} />
        </dl>
      </Panel>

      <Points
        title="What is going right"
        empty="Nothing the bank can show yet - that changes as reviews come back right."
        points={report.doing_well}
        questionText={questionText}
      />
      <Points
        title="What keeps going wrong"
        empty="No recurring habit stands out yet."
        points={report.going_wrong}
        questionText={questionText}
      />

      {report.next_steps.length > 0 && (
        <Section title="This week">
          <Panel className="px-6 py-5">
            <ol className="list-decimal space-y-1.5 pl-5 text-sm">
              {report.next_steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          </Panel>
        </Section>
      )}

      {stats.by_reason.length > 0 && (
        <Section title="Why you got them wrong" description="Counted from your debriefs.">
          <Panel className="px-6 py-5">
            <ul className="space-y-1 text-sm">
              {stats.by_reason.map((count) => (
                <li key={count.label} className="flex justify-between gap-4">
                  <span>{count.label}</span>
                  <span className="text-muted-foreground tabular-nums">{count.count}</span>
                </li>
              ))}
            </ul>
          </Panel>
        </Section>
      )}

      <p className="text-xs text-muted-foreground">
        Written by {ANALYZER_LABELS[insight.analyzer] ?? insight.analyzer} on{" "}
        {format(new Date(insight.created_at), "d MMM yyyy, HH:mm")}, from{" "}
        {insight.question_count} question{insight.question_count === 1 ? "" : "s"}.
      </p>
    </article>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-xl font-semibold tabular-nums">{value}</dd>
    </div>
  );
}

function Points({
  title,
  empty,
  points,
  questionText,
}: {
  title: string;
  empty: string;
  points: CoachPoint[];
  questionText: Map<string, string>;
}) {
  return (
    <Section title={title}>
      {points.length === 0 ? (
        <p className="text-sm text-muted-foreground">{empty}</p>
      ) : (
        <div className="space-y-3">
          {points.map((point) => (
            <Panel key={point.title} className="px-6 py-4">
              <h3 className="font-medium">{point.title}</h3>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                {point.detail}
              </p>
              {point.question_ids.length > 0 && (
                <ul className="mt-3 space-y-1">
                  {point.question_ids.map((id) => (
                    <li key={id}>
                      <Link
                        href={`/bank/${id}`}
                        className="line-clamp-1 text-sm text-azurite-deep underline-offset-2 hover:underline dark:text-azurite"
                      >
                        {questionText.get(id) ?? "Open the question"}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          ))}
        </div>
      )}
    </Section>
  );
}
