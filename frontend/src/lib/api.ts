import type {
  Answer,
  BankQuery,
  DueReview,
  ErrorType,
  Mistake,
  MistakeDraft,
  MistakeEdit,
  ReviewCompleteResult,
  Section,
  Stats,
  StudentOutcome,
  Urgency,
} from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    // Only declare a JSON body when there is one. A Content-Type on a bare GET
    // makes it a non-simple request, which costs a CORS preflight per read.
    headers: init?.body
      ? { "Content-Type": "application/json", ...init.headers }
      : init?.headers,
  });

  if (!response.ok) {
    // FastAPI puts the readable part in `detail`; fall back to the status line.
    const detail = await response
      .json()
      .then((body) => body?.detail)
      .catch(() => null);
    throw new ApiError(
      typeof detail === "string" ? detail : response.statusText,
      response.status,
    );
  }

  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

export interface MistakeFilters {
  error_type?: ErrorType;
  urgency?: Urgency;
  section?: Section;
  topic?: string;
  q?: string;
}

function query(filters: MistakeFilters): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value);
  }
  const encoded = params.toString();
  return encoded ? `?${encoded}` : "";
}

export const api = {
  /** `analyze: false` logs the question and leaves the debrief to be asked for later. */
  logMistake: (draft: MistakeDraft, analyze = true) =>
    request<Mistake>(`/mistakes?analyze=${analyze}`, {
      method: "POST",
      body: JSON.stringify(draft),
    }),

  updateMistake: (id: string, edit: MistakeEdit) =>
    request<Mistake>(`/mistakes/${id}`, { method: "PATCH", body: JSON.stringify(edit) }),

  listMistakes: (filters: MistakeFilters = {}) =>
    request<Mistake[]>(`/mistakes${query(filters)}`),

  /** Multi-facet filter: OR within a facet, AND across them. */
  searchMistakes: (query: Partial<BankQuery>) =>
    request<Mistake[]>("/mistakes/search", {
      method: "POST",
      body: JSON.stringify(query),
    }),

  getMistake: (id: string) => request<Mistake>(`/mistakes/${id}`),

  /** Ask the AI to debrief this question. `force` overwrites an analysis you edited. */
  analyze: (id: string, force = false) =>
    request<Mistake>(`/mistakes/${id}/analyze?force=${force}`, { method: "POST" }),

  deleteMistake: (id: string) => request<void>(`/mistakes/${id}`, { method: "DELETE" }),

  dueReviews: () => request<DueReview[]>("/reviews/due"),

  upcomingReviews: () => request<DueReview[]>("/reviews/upcoming"),

  completeReview: (id: string, outcome: StudentOutcome) =>
    request<ReviewCompleteResult>(`/reviews/${id}/complete`, {
      method: "POST",
      body: JSON.stringify({ outcome }),
    }),

  stats: () => request<Stats>("/stats"),

  /** Ask a question about the bank. The model writes the filter; the rows are real. */
  ask: (question: string) =>
    request<Answer>("/ask", { method: "POST", body: JSON.stringify({ question }) }),
};

/** Query keys, in one place so mutations can invalidate precisely. */
export const keys = {
  mistakes: (filters: MistakeFilters = {}) => ["mistakes", filters] as const,
  search: (query: Partial<BankQuery>) => ["mistakes", "search", query] as const,
  mistake: (id: string) => ["mistake", id] as const,
  due: () => ["reviews", "due"] as const,
  upcoming: () => ["reviews", "upcoming"] as const,
  stats: () => ["stats"] as const,
};
