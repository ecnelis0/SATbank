import type { DueReview, Mistake, ReviewEvent } from "@/lib/types";

const HOUR = 3600_000;

export function makeReview(overrides: Partial<ReviewEvent> = {}): ReviewEvent {
  return {
    id: `r-${overrides.interval_label ?? "1h"}-${overrides.cycle ?? 0}`,
    cycle: 0,
    step_index: 0,
    interval_label: "1h",
    due_at: new Date(Date.now() + HOUR).toISOString(),
    completed_at: null,
    outcome: null,
    ...overrides,
  };
}

/** A full five-rung ladder anchored `hoursAgo` in the past. */
export function makeLadder(hoursAgo = 0, cycle = 0): ReviewEvent[] {
  const anchor = Date.now() - hoursAgo * HOUR;
  return (
    [
      ["1h", 1],
      ["24h", 24],
      ["72h", 72],
      ["1w", 24 * 7],
      ["1mo", 24 * 30],
    ] as const
  ).map(([label, hours], index) =>
    makeReview({
      id: `r-${label}-${cycle}`,
      cycle,
      step_index: index,
      interval_label: label,
      due_at: new Date(anchor + hours * HOUR).toISOString(),
    }),
  );
}

export function makeMistake(overrides: Partial<Mistake> = {}): Mistake {
  return {
    id: "m1",
    created_at: new Date().toISOString(),
    section: "math",
    source: "Bluebook Practice Test 4",
    question_text: "If 3x + 7 = 22, what is the value of x?",
    choices: ["3", "5", "7", "15"],
    your_answer: "7",
    correct_answer: "5",
    student_note: null,
    analysis_status: "ready",
    analysis_error: null,
    analyzed_at: new Date().toISOString(),
    analyzed_by: "stub",
    analysis_edited_at: null,
    error_type: "careless_arithmetic",
    topic: "linear equations",
    difficulty: "medium",
    urgency: "important",
    why_wrong: "You solved for 3x and stopped there.",
    correct_reasoning: "Subtract 7, then divide by 3.",
    takeaway: "Finish the division before you pick.",
    trap: "7 is what you get if you stop at 3x = 15 and read off the 15's factor.",
    tags: ["algebra"],
    reviews: makeLadder(),
    ...overrides,
  };
}

export function makeDueReview(overrides: Partial<Mistake> = {}): DueReview {
  const mistake = makeMistake({ reviews: makeLadder(2), ...overrides });
  return { review: mistake.reviews[0], mistake };
}
