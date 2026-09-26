import { beforeEach, describe, expect, it } from "vitest";

import {
  clearDraft,
  getDraft,
  isWorthKeeping,
  saveChoicesOfFiling,
  saveValues,
} from "@/components/app/log-draft";

beforeEach(() => {
  window.localStorage.clear();
  clearDraft();
});

describe("the log draft", () => {
  it("keeps what was typed", () => {
    saveValues({ question_text: "If 3x + 7 = 22…", your_answer: "15" });
    expect(getDraft().values).toEqual({ question_text: "If 3x + 7 = 22…", your_answer: "15" });
  });

  it("keeps tags and concepts alongside the typed fields", () => {
    saveValues({ question_text: "A question" });
    saveChoicesOfFiling({ tags: ["by mistake"] });
    saveChoicesOfFiling({ conceptIds: ["abc"] });

    const draft = getDraft();
    expect(draft.values).toEqual({ question_text: "A question" });
    expect(draft.tags).toEqual(["by mistake"]);
    expect(draft.conceptIds).toEqual(["abc"]);
  });

  it("is empty again after clearing, and stays empty", () => {
    // The regression this exists for: "nothing cached" and "nothing stored" were
    // both null, so the read after a clear decided its stale copy was still good
    // and handed back the draft that had just been thrown away.
    saveValues({ question_text: "Something I typed" });
    expect(isWorthKeeping(getDraft())).toBe(true);

    clearDraft();

    expect(getDraft().values).toEqual({});
    expect(getDraft().tags).toEqual([]);
    expect(isWorthKeeping(getDraft())).toBe(false);
  });

  it("survives a corrupt entry rather than taking the form down", () => {
    window.localStorage.setItem("mistake-bank:log-draft", "{not json");
    expect(getDraft().values).toEqual({});
  });
});

describe("isWorthKeeping", () => {
  it("does not count the form's own defaults as a draft", () => {
    // Arriving at the page fresh must not announce that it restored something.
    expect(isWorthKeeping({ values: { section: "math", urgency: "ai" }, tags: [], conceptIds: [] }))
      .toBe(false);
  });

  it("ignores whitespace", () => {
    expect(isWorthKeeping({ values: { question_text: "   " }, tags: [], conceptIds: [] })).toBe(
      false,
    );
  });

  it("counts a typed field, a tag or a concept", () => {
    expect(isWorthKeeping({ values: { your_answer: "B" }, tags: [], conceptIds: [] })).toBe(true);
    expect(isWorthKeeping({ values: {}, tags: ["guessed"], conceptIds: [] })).toBe(true);
    expect(isWorthKeeping({ values: {}, tags: [], conceptIds: ["x"] })).toBe(true);
  });
});
