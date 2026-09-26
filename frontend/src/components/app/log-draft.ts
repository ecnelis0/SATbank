/** The half-written question on the log form, kept across navigation.
 *
 *  Leaving the tab to look something up — what the answer was, which concept this
 *  belongs under — used to throw the whole form away. The draft is written to
 *  localStorage as you type and cleared the moment the question is logged, so the
 *  only way to lose it is to ask.
 *
 *  Text only. The pending screenshots are `File` objects and there is no honest
 *  way to put those in localStorage: a 10MB picture does not fit in a 5MB budget,
 *  and silently dropping some of them would be worse than not trying.
 *
 *  Shaped as an external store, for the same reason `page-theme.tsx` is: the
 *  obvious version — `useState` plus an effect that reads storage on mount — sets
 *  state inside an effect, which this project's lint rejects outright.
 */

const KEY = "mistake-bank:log-draft";

export interface LogDraft {
  values: Record<string, unknown>;
  tags: string[];
  conceptIds: string[];
}

const EMPTY: LogDraft = { values: {}, tags: [], conceptIds: [] };

/** "Nothing is cached" has to be a value `localStorage.getItem` can never return,
 *  and it returns `null` for a key that is not there. Using null for both meant
 *  that clearing the draft (which invalidates the cache) and then reading it
 *  (which finds no key) compared null to null, decided the cache was still good,
 *  and handed back the draft that had just been cleared. */
const UNREAD = Symbol("unread");

let cachedRaw: string | null | typeof UNREAD = UNREAD;
let cachedValue: LogDraft = EMPTY;
const listeners = new Set<() => void>();

/** Memoised on the raw string: `useSyncExternalStore` re-renders forever if the
 *  snapshot is a fresh object every call. */
export function getDraft(): LogDraft {
  if (typeof window === "undefined") return EMPTY;
  const raw = window.localStorage.getItem(KEY);
  if (raw === cachedRaw) return cachedValue;
  cachedRaw = raw;
  if (!raw) {
    cachedValue = EMPTY;
    return cachedValue;
  }
  try {
    const parsed = JSON.parse(raw) as Partial<LogDraft>;
    cachedValue = {
      values:
        parsed.values && typeof parsed.values === "object"
          ? (parsed.values as Record<string, unknown>)
          : {},
      tags: Array.isArray(parsed.tags) ? parsed.tags : [],
      conceptIds: Array.isArray(parsed.conceptIds) ? parsed.conceptIds : [],
    };
  } catch {
    // A corrupt entry must not take the log form down with it.
    window.localStorage.removeItem(KEY);
    cachedRaw = UNREAD;
    cachedValue = EMPTY;
  }
  return cachedValue;
}

export function getServerDraft(): LogDraft {
  return EMPTY;
}

export function subscribe(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => {
    listeners.delete(onChange);
  };
}

function write(draft: LogDraft, notify: boolean): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(draft));
  } catch {
    // Quota. The form still works; it just will not survive the next tab.
  }
  cachedRaw = UNREAD;
  if (notify) for (const listener of listeners) listener();
}

/** Save the typed fields. Deliberately silent: this runs on every keystroke, and
 *  waking the subscribers each time would re-render the form mid-typing — and, via
 *  the effect that calls this, loop. */
export function saveValues(values: Record<string, unknown>): void {
  write({ ...getDraft(), values }, false);
}

/** Save a picked tag or concept. These come from event handlers and do need the
 *  re-render, because the chips are rendered from the store. */
export function saveChoicesOfFiling(
  patch: Partial<Pick<LogDraft, "tags" | "conceptIds">>,
): void {
  write({ ...getDraft(), ...patch }, true);
}

export function clearDraft(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(KEY);
  cachedRaw = UNREAD;
  for (const listener of listeners) listener();
}

/** Whether there is anything worth restoring.
 *
 *  The form's own defaults (Math, "let the AI decide") are not a draft — without
 *  this, arriving at the page fresh would restore an empty form over itself. */
export function isWorthKeeping(draft: LogDraft): boolean {
  if (draft.tags.length > 0 || draft.conceptIds.length > 0) return true;
  return Object.entries(draft.values).some(([key, value]) => {
    if (key === "section" || key === "urgency") return false;
    return typeof value === "string" && value.trim().length > 0;
  });
}
