import type { BankQuery, ErrorType, Section, Urgency } from "./types";

/** The facets the bank can be sliced by. Each holds a list: OR inside, AND across. */
export interface Facets {
  urgency: Urgency[];
  section: Section[];
  error_type: ErrorType[];
  topics: string[];
  text: string;
}

export const NO_FACETS: Facets = {
  urgency: [],
  section: [],
  error_type: [],
  topics: [],
  text: "",
};

export function isEmpty(facets: Facets): boolean {
  return (
    facets.urgency.length === 0 &&
    facets.section.length === 0 &&
    facets.error_type.length === 0 &&
    facets.topics.length === 0 &&
    facets.text.trim() === ""
  );
}

export function countSelected(facets: Facets): number {
  return (
    facets.urgency.length +
    facets.section.length +
    facets.error_type.length +
    facets.topics.length
  );
}

/** Add or remove one value, leaving the other facets alone. */
export function toggle<K extends "urgency" | "section" | "error_type" | "topics">(
  facets: Facets,
  key: K,
  value: Facets[K][number],
): Facets {
  const current = facets[key] as string[];
  const next = current.includes(value)
    ? current.filter((item) => item !== value)
    : [...current, value];
  return { ...facets, [key]: next };
}

export function has(facets: Facets, key: keyof Facets, value: string): boolean {
  const current = facets[key];
  return Array.isArray(current) && (current as string[]).includes(value);
}

/** Facets <-> the URL, so a filtered view is a link you can share or go back to. */
export function toSearchParams(facets: Facets): URLSearchParams {
  const params = new URLSearchParams();
  for (const value of facets.urgency) params.append("urgency", value);
  for (const value of facets.section) params.append("section", value);
  for (const value of facets.error_type) params.append("error_type", value);
  for (const value of facets.topics) params.append("topic", value);
  if (facets.text.trim()) params.set("q", facets.text.trim());
  return params;
}

export function fromSearchParams(params: URLSearchParams | ReadonlyURLSearchParamsLike): Facets {
  return {
    urgency: params.getAll("urgency") as Urgency[],
    section: params.getAll("section") as Section[],
    error_type: params.getAll("error_type") as ErrorType[],
    topics: params.getAll("topic"),
    text: params.get("q") ?? "",
  };
}

/** Next's `useSearchParams` returns a read-only shape rather than a URLSearchParams. */
interface ReadonlyURLSearchParamsLike {
  getAll(name: string): string[];
  get(name: string): string | null;
}

export function toQuery(facets: Facets): Partial<BankQuery> {
  return {
    urgency: facets.urgency,
    section: facets.section,
    error_type: facets.error_type,
    topics: facets.topics,
    text: facets.text.trim() || null,
    sort: "newest",
    limit: 100,
  };
}
