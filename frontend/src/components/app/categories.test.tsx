import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Categories } from "@/components/app/categories";
import { api } from "@/lib/api";
import type { Stats } from "@/lib/types";
import { renderWithQuery } from "@/test/render";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const CONCEPTS = [
  {
    id: "c1",
    title: "Circumference gives the radius",
    body: null,
    section: "math" as const,
    created_at: new Date().toISOString(),
    updated_at: null,
    question_count: 2,
    images: [],
  },
  {
    id: "c2",
    title: "inverse trig",
    body: null,
    section: null,
    created_at: new Date().toISOString(),
    updated_at: null,
    question_count: 0,
    images: [],
  },
];

const STATS: Stats = {
  total_mistakes: 6,
  due_now: 1,
  untagged_questions: 2,
  reviews_completed: 0,
  by_error_type: [
    { key: "concept_gap", count: 3 },
    { key: "careless_arithmetic", count: 2 },
  ],
  by_concept: [{ key: "Circumference gives the radius", count: 2 }],
  by_urgency: [
    { key: "fundamental", count: 1 },
    { key: "very_important", count: 3 },
  ],
  by_section: [
    { key: "math", count: 4 },
    { key: "reading_writing", count: 2 },
  ],
  topics: [
    { section: "math", topic: "math fundamentals", count: 3 },
    { section: "math", topic: "circles", count: 1 },
    { section: "reading_writing", topic: "command of evidence", count: 2 },
  ],
};

async function open() {
  vi.spyOn(api, "stats").mockResolvedValue(STATS);
  vi.spyOn(api, "listConcepts").mockResolvedValue(CONCEPTS);
  const user = userEvent.setup();
  renderWithQuery(<Categories />);
  await screen.findByText("How urgent");
  return user;
}

describe("Categories", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    push.mockClear();
  });

  it("keeps topics folded away until their section is expanded", async () => {
    const user = await open();

    expect(screen.queryByText("math fundamentals")).not.toBeInTheDocument();
    expect(screen.queryByText("command of evidence")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Expand Math" }));

    expect(screen.getByText("math fundamentals")).toBeInTheDocument();
    expect(screen.getByText("circles")).toBeInTheDocument();
    // Only that section's topics - the other folder stays shut.
    expect(screen.queryByText("command of evidence")).not.toBeInTheDocument();
  });

  it("puts each topic under the section it belongs to", async () => {
    const user = await open();
    await user.click(screen.getByRole("button", { name: "Expand Reading & Writing" }));

    expect(screen.getByText("command of evidence")).toBeInTheDocument();
    expect(screen.queryByText("math fundamentals")).not.toBeInTheDocument();
  });

  it("collapses again", async () => {
    const user = await open();
    await user.click(screen.getByRole("button", { name: "Expand Math" }));
    await user.click(screen.getByRole("button", { name: "Collapse Math" }));

    expect(screen.queryByText("circles")).not.toBeInTheDocument();
  });

  it("will not offer to expand a section with no topics", async () => {
    vi.spyOn(api, "stats").mockResolvedValue({ ...STATS, topics: [] });
    renderWithQuery(<Categories />);
    await screen.findByText("How urgent");

    expect(screen.getByRole("button", { name: "Expand Math" })).toBeDisabled();
  });

  it("selects across facets at once and sends all four to the bank", async () => {
    const user = await open();

    await user.click(screen.getByRole("checkbox", { name: /Very important/ }));
    await user.click(screen.getByRole("checkbox", { name: /^Math/ }));
    await user.click(screen.getByRole("button", { name: "Expand Math" }));
    await user.click(screen.getByRole("checkbox", { name: /math fundamentals/ }));
    await user.click(screen.getByRole("checkbox", { name: /Concept gap/ }));

    await user.click(screen.getByRole("button", { name: "Show 4 filters" }));

    await waitFor(() => expect(push).toHaveBeenCalled());
    const url = new URL(push.mock.calls[0][0], "http://x");
    expect(url.pathname).toBe("/bank");
    expect(url.searchParams.getAll("urgency")).toEqual(["very_important"]);
    expect(url.searchParams.getAll("section")).toEqual(["math"]);
    expect(url.searchParams.getAll("topic")).toEqual(["math fundamentals"]);
    expect(url.searchParams.getAll("error_type")).toEqual(["concept_gap"]);
  });

  it("shows a selection as checked, and unchecks it again", async () => {
    const user = await open();
    const box = screen.getByRole("checkbox", { name: /Fundamental concept/ });

    expect(box).toHaveAttribute("aria-checked", "false");
    await user.click(box);
    expect(box).toHaveAttribute("aria-checked", "true");
    await user.click(box);
    expect(box).toHaveAttribute("aria-checked", "false");
  });

  it("clears every selection at once", async () => {
    const user = await open();
    await user.click(screen.getByRole("checkbox", { name: /Very important/ }));
    await user.click(screen.getByRole("checkbox", { name: /Concept gap/ }));
    expect(screen.getByRole("button", { name: "Show 2 filters" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Clear" }));

    expect(screen.getByRole("button", { name: "Show questions" })).toBeDisabled();
  });

  it("shows how many questions sit behind each row", async () => {
    const user = await open();
    const math = screen.getByRole("checkbox", { name: /^Math/ });
    expect(within(math).getByText("4")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Expand Math" }));
    const topic = screen.getByRole("checkbox", { name: /math fundamentals/ });
    expect(within(topic).getByText("3")).toBeInTheDocument();
  });
});


describe("Categories concepts", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    push.mockClear();
  });

  it("warns that a concept has nothing tagged, rather than letting you find out by clicking", async () => {
    await open();

    const empty = await screen.findByRole("checkbox", { name: /inverse trig/ });
    expect(within(empty).getByText("nothing tagged")).toBeInTheDocument();

    // The one that does have questions is not marked.
    const full = screen.getByRole("checkbox", { name: /Circumference gives the radius/ });
    expect(within(full).queryByText("nothing tagged")).not.toBeInTheDocument();
  });

  it("offers the questions filed under no concept at all", async () => {
    const user = await open();

    await user.click(await screen.findByRole("checkbox", { name: /No concept yet/ }));
    await user.click(screen.getByRole("button", { name: "Show 1 filter" }));

    const url = new URL(push.mock.calls[0][0], "http://x");
    expect(url.searchParams.get("tagged")).toBe("0");
  });

  it("filters by a concept id, not by its title", async () => {
    const user = await open();

    await user.click(
      await screen.findByRole("checkbox", { name: /Circumference gives the radius/ }),
    );
    await user.click(screen.getByRole("button", { name: "Show 1 filter" }));

    const url = new URL(push.mock.calls[0][0], "http://x");
    expect(url.searchParams.getAll("concept")).toEqual(["c1"]);
  });
});
