/** Mirrors `backend/app/schemas.py`. Keep the two in step. */

export type Section = "reading_writing" | "math";

export const ERROR_TYPES = [
  "careless_arithmetic",
  "misread_question",
  "concept_gap",
  "formula_error",
  "algebra_slip",
  "unit_or_conversion",
  "trap_answer",
  "evidence_misread",
  "vocabulary_gap",
  "grammar_rule_gap",
  "time_pressure_guess",
  "other",
] as const;
export type ErrorType = (typeof ERROR_TYPES)[number];

export type Difficulty = "easy" | "medium" | "hard";
export type AnalysisStatus = "not_requested" | "pending" | "ready" | "failed";
export type ReviewOutcome = "correct" | "wrong" | "skipped" | "superseded";
/** What the student can actually answer with. `superseded` is the ladder's own. */
export type StudentOutcome = Exclude<ReviewOutcome, "superseded">;

export interface ReviewEvent {
  id: string;
  cycle: number;
  step_index: number;
  interval_label: string;
  due_at: string;
  completed_at: string | null;
  outcome: ReviewOutcome | null;
}

export interface Mistake {
  id: string;
  created_at: string;
  section: Section;
  source: string | null;
  question_text: string;
  choices: string[] | null;
  your_answer: string;
  correct_answer: string;
  student_note: string | null;

  analysis_status: AnalysisStatus;
  analysis_error: string | null;
  analyzed_at: string | null;
  analyzed_by: string | null;
  analysis_edited_at: string | null;
  error_type: ErrorType | null;
  topic: string | null;
  difficulty: Difficulty | null;
  why_wrong: string | null;
  correct_reasoning: string | null;
  takeaway: string | null;
  trap: string | null;
  tags: string[] | null;

  reviews: ReviewEvent[];
}

export interface DueReview {
  review: ReviewEvent;
  mistake: Mistake;
}

export interface ReviewCompleteResult {
  review: ReviewEvent;
  ladder_restarted: boolean;
  next_due_at: string | null;
}

export interface SlotCount {
  key: string;
  count: number;
}

export interface Stats {
  total_mistakes: number;
  due_now: number;
  reviews_completed: number;
  by_error_type: SlotCount[];
  by_topic: SlotCount[];
  by_section: SlotCount[];
}

/** Every field is editable; only the keys sent are changed. */
export type MistakeEdit = Partial<
  Pick<
    Mistake,
    | "section"
    | "source"
    | "question_text"
    | "choices"
    | "your_answer"
    | "correct_answer"
    | "student_note"
    | "error_type"
    | "topic"
    | "difficulty"
    | "why_wrong"
    | "correct_reasoning"
    | "takeaway"
    | "trap"
    | "tags"
  >
>;

export interface MistakeDraft {
  section: Section;
  question_text: string;
  your_answer: string;
  correct_answer: string;
  choices?: string[] | null;
  source?: string | null;
  student_note?: string | null;
}
