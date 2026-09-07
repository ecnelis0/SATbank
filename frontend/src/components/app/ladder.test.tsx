import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Ladder } from "@/components/app/ladder";
import { makeLadder } from "@/test/fixtures";

describe("Ladder", () => {
  it("shows all five rungs, in schedule order", () => {
    render(<Ladder reviews={makeLadder()} />);

    const rungs = within(screen.getByRole("list", { name: "Review schedule" })).getAllByRole(
      "listitem",
    );
    expect(rungs.map((li) => li.textContent)).toEqual([
      expect.stringContaining("1 hour"),
      expect.stringContaining("24 hours"),
      expect.stringContaining("72 hours"),
      expect.stringContaining("1 week"),
      expect.stringContaining("1 month"),
    ]);
  });

  it("calls out the rung that is due and leaves the rest counting down", () => {
    render(<Ladder reviews={makeLadder(2)} />);

    expect(screen.getAllByText("due now")).toHaveLength(1);
    expect(screen.getAllByText(/^in /)).toHaveLength(4);
  });

  it("shows only the newest cycle after a miss restarts the ladder", () => {
    // The realistic shape: cycle 0 was answered wrong at the 1h rung and superseded,
    // and cycle 1 was armed from that moment.
    const first = makeLadder(2, 0).map((rung, index) => ({
      ...rung,
      completed_at: new Date().toISOString(),
      outcome: index === 0 ? ("wrong" as const) : ("superseded" as const),
    }));
    render(<Ladder reviews={[...first, ...makeLadder(0, 1)]} />);

    const rungs = within(screen.getByRole("list", { name: "Review schedule" })).getAllByRole(
      "listitem",
    );
    expect(rungs).toHaveLength(5);
    // Cycle 1 is entirely ahead of us, so nothing reads as done or missed.
    expect(screen.queryByText("missed")).not.toBeInTheDocument();
    expect(screen.getByText(/Ladder restarted once/)).toBeInTheDocument();
  });

  it("marks an answered rung as done and a missed one as missed", () => {
    const rungs = makeLadder(48);
    rungs[0] = { ...rungs[0], completed_at: new Date().toISOString(), outcome: "correct" };
    rungs[1] = { ...rungs[1], completed_at: new Date().toISOString(), outcome: "wrong" };
    render(<Ladder reviews={rungs} />);

    expect(screen.getByText("done")).toBeInTheDocument();
    expect(screen.getByText("missed")).toBeInTheDocument();
  });
});
