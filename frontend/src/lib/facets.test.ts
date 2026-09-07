import { describe, expect, it } from "vitest";

import {
  countSelected,
  fromSearchParams,
  has,
  isEmpty,
  toQuery,
  toSearchParams,
  toggle,
  type Facets,
  NO_FACETS,
} from "@/lib/facets";

const PICKED: Facets = {
  urgency: ["very_important"],
  section: ["math"],
  error_type: ["concept_gap"],
  topics: ["math fundamentals"],
  text: "",
};

describe("facets", () => {
  it("toggling adds then removes, leaving the other facets alone", () => {
    const added = toggle(NO_FACETS, "urgency", "fundamental");
    expect(added.urgency).toEqual(["fundamental"]);
    expect(added.section).toEqual([]);

    expect(toggle(added, "urgency", "fundamental").urgency).toEqual([]);
  });

  it("holds several values in one facet", () => {
    const two = toggle(toggle(NO_FACETS, "urgency", "fundamental"), "urgency", "important");

    expect(two.urgency).toEqual(["fundamental", "important"]);
  });

  it("survives the round trip through the URL", () => {
    const params = toSearchParams(PICKED);

    expect(fromSearchParams(params)).toEqual({ ...PICKED, text: "" });
  });

  it("puts each value in its own parameter, so commas in a topic are safe", () => {
    const params = toSearchParams({ ...NO_FACETS, topics: ["rates, ratios", "circles"] });

    expect(params.getAll("topic")).toEqual(["rates, ratios", "circles"]);
    expect(fromSearchParams(params).topics).toEqual(["rates, ratios", "circles"]);
  });

  it("reads a single-value link from the dashboard", () => {
    const facets = fromSearchParams(new URLSearchParams("urgency=fundamental"));

    expect(facets.urgency).toEqual(["fundamental"]);
    expect(countSelected(facets)).toBe(1);
  });

  it("knows when nothing is selected", () => {
    expect(isEmpty(NO_FACETS)).toBe(true);
    expect(isEmpty({ ...NO_FACETS, text: "  " })).toBe(true);
    expect(isEmpty(PICKED)).toBe(false);
    expect(countSelected(PICKED)).toBe(4);
  });

  it("becomes the query the backend runs", () => {
    const query = toQuery({ ...PICKED, text: "  circle  " });

    expect(query).toMatchObject({
      urgency: ["very_important"],
      section: ["math"],
      error_type: ["concept_gap"],
      topics: ["math fundamentals"],
      text: "circle",
    });
  });

  it("sends no text rather than an empty string", () => {
    expect(toQuery({ ...NO_FACETS, text: "   " }).text).toBeNull();
  });

  it("has() only reports a value that is actually selected", () => {
    expect(has(PICKED, "section", "math")).toBe(true);
    expect(has(PICKED, "section", "reading_writing")).toBe(false);
  });
});
