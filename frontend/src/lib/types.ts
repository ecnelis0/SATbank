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

/** How badly a question needs revisiting. Ordered most urgent first. */
export const URGENCIES = ["fundamental", "very_important", "important"] as const;
export type Urgency = (typeof URGENCIES)[number];
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

export interface TagCount {
  tag: string;
  count: number;
  /** True while nothing carries it — a starting suggestion, not a chosen tag. */
  suggested: boolean;
}

export interface ConceptSummary {
  id: string;
  title: string;
}

export interface Concept extends ConceptSummary {
  created_at: string;
  updated_at: string | null;
  body: string | null;
  section: Section | null;
  question_count: number;
  images: MistakeImage[];
}

export interface ConceptDetail extends Concept {
  mistakes: Mistake[];
}

export interface ConceptDraft {
  title: string;
  body?: string | null;
  section?: Section | null;
}

export interface MistakeImage {
  id: string;
  url: string;
  content_type: string;
  byte_size: number;
  width: number | null;
  height: number | null;
  caption: string | null;
  position: number;
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
  urgency: Urgency | null;
  urgency_is_yours: boolean;
  why_wrong: string | null;
  correct_reasoning: string | null;
  takeaway: string | null;
  trap: string | null;
  tags: string[] | null;

  reviews: ReviewEvent[];
  concepts: ConceptSummary[];
  images: MistakeImage[];
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

export interface TopicCount {
  section: Section;
  topic: string;
  count: number;
}

export interface Stats {
  total_mistakes: number;
  due_now: number;
  untagged_questions: number;
  reviews_completed: number;
  by_error_type: SlotCount[];
  by_urgency: SlotCount[];
  by_concept: SlotCount[];
  by_section: SlotCount[];
  topics: TopicCount[];
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
    | "urgency"
    | "why_wrong"
    | "correct_reasoning"
    | "takeaway"
    | "trap"
    | "tags"
  >
>;

export type BankSort = "newest" | "oldest" | "most_urgent";

/** Mirrors `backend/app/query.py`. The assistant's reading of your sentence. */
export interface BankQuery {
  concept_ids: string[];
  concepts: string[];
  tags: string[];
  urgency: Urgency[];
  error_type: ErrorType[];
  section: Section[];
  topics: string[];
  text: string | null;
  logged_after: string | null;
  logged_before: string | null;
  only_due: boolean;
  has_concept: boolean | null;
  sort: BankSort;
  limit: number;
}

export interface Answer {
  question: string;
  answer: string;
  analyzer: string;
  analyzer_ready: boolean;
  filter_description: string;
  query: BankQuery;
  mistakes: Mistake[];
  error: string | null;
}

export interface MistakeDraft {
  section: Section;
  urgency?: Urgency | null;
  concept_ids?: string[];
  tags?: string[];
  question_text: string;
  your_answer: string;
  correct_answer: string;
  choices?: string[] | null;
  source?: string | null;
  student_note?: string | null;
}
