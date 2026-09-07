import { describe, expect, it } from "vitest";

import { parseChoices } from "@/components/app/mistake-form";

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
});
