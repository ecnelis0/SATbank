import type { ErrorType, Section, Urgency } from "./types";

/** The slot names the student reads. The keys are the AI's closed vocabulary. */
export const ERROR_TYPE_LABELS: Record<ErrorType, string> = {
  careless_arithmetic: "Careless arithmetic",
  misread_question: "Misread the question",
  concept_gap: "Concept gap",
  formula_error: "Wrong formula",
  algebra_slip: "Algebra slip",
  unit_or_conversion: "Units & conversion",
  trap_answer: "Walked into the trap",
  evidence_misread: "Misread the evidence",
  vocabulary_gap: "Vocabulary gap",
  grammar_rule_gap: "Grammar rule gap",
  time_pressure_guess: "Guessed under time pressure",
  other: "Something else",
};

export const ERROR_TYPE_BLURBS: Record<ErrorType, string> = {
  careless_arithmetic: "You knew the method. The numbers went wrong on the way.",
  misread_question: "You solved a question. Just not the one that was asked.",
  concept_gap: "The idea underneath this question is not yet solid.",
  formula_error: "The right shape of answer, reached with the wrong formula.",
  algebra_slip: "A sign, a term, or a step that got lost in the manipulation.",
  unit_or_conversion: "The quantity was right, the unit was not.",
  trap_answer: "You picked the answer the question was built to make attractive.",
  evidence_misread: "The lines you chose do not say what you took them to say.",
  vocabulary_gap: "A word in the passage or the answers did the damage.",
  grammar_rule_gap: "A rule of punctuation or structure that has not landed yet.",
  time_pressure_guess: "Not a knowledge problem. A clock problem.",
  other: "Does not fit the usual slots.",
};

export const URGENCY_LABELS: Record<Urgency, string> = {
  fundamental: "Fundamental concept",
  very_important: "Very important",
  important: "Important",
};

export const URGENCY_BLURBS: Record<Urgency, string> = {
  fundamental: "This is holding up everything built on top of it. Fix it first.",
  very_important: "A skill or trap you will meet again. Worth real attention.",
  important: "Worth coming back to, but not what is costing you the most.",
};

/** One colour per level, loud to quiet, so the three read as a scale rather than
 *  three identical chips. Mirrors the Figma "urgency/*" tokens. */
export const URGENCY_STYLES: Record<Urgency, string> = {
  fundamental: "border-transparent bg-destructive/10 text-destructive",
  very_important:
    "border-transparent bg-amber-500/12 text-amber-800 dark:text-amber-300",
  important: "border-border bg-muted text-muted-foreground",
};

export const SECTION_LABELS: Record<Section, string> = {
  reading_writing: "Reading & Writing",
  math: "Math",
};

/** Reads better than the raw interval keys the API returns. */
export const INTERVAL_LABELS: Record<string, string> = {
  "1h": "1 hour",
  "24h": "24 hours",
  "72h": "72 hours",
  "1w": "1 week",
  "1mo": "1 month",
};

export const LADDER: readonly string[] = ["1h", "24h", "72h", "1w", "1mo"];
