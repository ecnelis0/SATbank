import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Recurring, timesMissedAgain } from "@/components/app/recurring";
import { api } from "@/lib/api";
import type { Mistake, ReviewEvent } from "@/lib/types";
import { makeLadder, makeMistake } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";

/** A ladder where the first rung was answered wrong `times` over, with the rungs
 *  each miss retired marked superseded - the shape the backend really produces. */
function missedAgain(times: number): ReviewEvent[] {
  const events: ReviewEvent[] = [];
  for (let cycle = 0; cycle < times; cycle++) {
    const rungs = makeLadder(2, cycle).map((rung, index) => ({
      ...rung,
      id: `r${cycle}-${index}`,
      completed_at: new Date().toISOString(),
      outcome: index === 0 ? ("wrong" as const) : ("superseded" as const),
    }));
    events.push(...rungs);
  }
  return events;
}

describe("timesMissedAgain", () => {
  it("counts the reviews answered wrong", () => {
    expect(timesMissedAgain(makeMistake({ reviews: missedAgain(3) }))).toBe(3);
  });

  it("does not count the rungs a restart retired", () => {
    // Three misses produce twelve superseded rungs. Counting those would say 15.
    const mistake = makeMistake({ reviews: missedAgain(3) });
    expect(mistake.reviews.filter((r) => r.outcome === "superseded")).toHaveLength(12);
    expect(timesMissedAgain(mistake)).toBe(3);
  });

  it("is zero for a question that has not come back wrong", () => {
    expect(timesMissedAgain(makeMistake())).toBe(0);
  });
});

describe("Recurring", () => {
  beforeEach(() => vi.restoreAllMocks());

  const trig = (): Mistake =>
    makeMistake({
      id: "m1",
      question_text: "arcsin(0.5) is which angle?",
      topic: "inverse trig",
      reviews: missedAgain(3),
    });

  const once = (): Mistake =>
    makeMistake({ id: "m2", question_text: "One-off slip", topic: "circles" });

  it("shows only what came back wrong, not everything logged", async () => {
    vi.spyOn(api, "listMistakes").mockResolvedValue([trig(), once()]);

    renderWithQuery(<Recurring />);

    expect(await screen.findByText("arcsin(0.5) is which angle?")).toBeInTheDocument();
    expect(screen.queryByText("One-off slip")).not.toBeInTheDocument();
  });

  it("says how many times, so a pattern is a number and not a vibe", async () => {
    vi.spyOn(api, "listMistakes").mockResolvedValue([trig()]);

    renderWithQuery(<Recurring />);

    expect(await screen.findByText("3× missed again")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /inverse trig · missed again 3×/ }),
    ).toHaveAttribute("href", "/bank?topic=inverse%20trig");
  });

  it("ranks the topic you keep missing above the one you missed once", async () => {
    const other = makeMistake({
      id: "m3",
      question_text: "Evidence question",
      topic: "command of evidence",
      reviews: missedAgain(1),
    });
    vi.spyOn(api, "listMistakes").mockResolvedValue([other, trig()]);

    renderWithQuery(<Recurring />);

    const links = await screen.findAllByRole("link", { name: /missed again/ });
    expect(links[0]).toHaveTextContent("inverse trig");
  });

  it("shows nothing at all when nothing has repeated", async () => {
    vi.spyOn(api, "listMistakes").mockResolvedValue([once()]);

    const { container } = renderWithQuery(<Recurring />);

    expect(screen.queryByText("What keeps coming back")).not.toBeInTheDocument();
    expect(container.textContent).toBe("");
  });
});
