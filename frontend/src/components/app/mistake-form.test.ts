import { describe, expect, it } from "vitest";

import { formatChoices, parseChoices } from "@/components/app/mistake-form";

describe("parseChoices", () => {
  it("turns one-per-line text into choices", () => {
    expect(parseChoices("3\n5\n7\n15")).toEqual(["3", "5", "7", "15"]);
  });

  it("ignores the blank lines and stray spacing a paste leaves behind", () => {
    expect(parseChoices("  3 \n\n 5  \n\n")).toEqual(["3", "5"]);
  });

  it("is null when the student did not enter choices", () => {
    expect(parseChoices("")).toBeNull();
    expect(parseChoices(undefined)).toBeNull();
    expect(parseChoices("   \n  ")).toBeNull();
  });

  it("strips the label off each choice, whichever way it was written", () => {
    // The app draws its own A/B/C/D, so a kept label renders as "A. A. 3".
    expect(parseChoices("A) 3\n\nB. 5\n\n(C) 7\n\nD: 15")).toEqual(["3", "5", "7", "15"]);
  });

  it("reads the blank-line layout the box now offers", () => {
    expect(parseChoices("A) 3\n\nB) 5\n\nC) 7\n\nD) 15")).toEqual(["3", "5", "7", "15"]);
  });

  it("keeps a choice that is only a letter", () => {
    // "Which section is it in?" answered A/B/C/D is a real question. Without a
    // separator and something after it, a letter is the choice, not a label.
    expect(parseChoices("A\nB\nC\nD")).toEqual(["A", "B", "C", "D"]);
  });

  it("leaves roman-numeral choices alone", () => {
    // Maths questions use "I", "II", "III" as options; stripping those would
    // silently empty them.
    expect(parseChoices("I) only\nII) only\nI and II")).toEqual([
      "I) only",
      "II) only",
      "I and II",
    ]);
  });

  it("does not eat a choice that happens to start with a letter and a full stop", () => {
    expect(parseChoices("A) x = 4\n\nB) y. z")).toEqual(["x = 4", "y. z"]);
  });
});

describe("formatChoices", () => {
  it("labels each choice and puts a blank line between them", () => {
    expect(formatChoices(["3", "5", "7", "15"])).toBe("A) 3\n\nB) 5\n\nC) 7\n\nD) 15");
  });

  it("round-trips with parseChoices, which is what a scan then a submit does", () => {
    const scanned = ["3", "5", "7", "15"];
    expect(parseChoices(formatChoices(scanned))).toEqual(scanned);
  });
});
