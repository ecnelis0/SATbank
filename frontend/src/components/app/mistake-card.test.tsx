import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MistakeCard } from "@/components/app/mistake-card";
import { makeLadder, makeMistake } from "@/test/fixtures";

describe("MistakeCard", () => {
  it("shows the slot the AI filed this under", () => {
    render(<MistakeCard mistake={makeMistake()} />);

    // One metadata line now: section · slot · topic, so match within it.
    expect(screen.getByText(/Careless arithmetic/)).toBeInTheDocument();
    expect(screen.getByText(/linear equations/)).toBeInTheDocument();
  });

  it("says a review is due rather than counting down to it", () => {
    render(<MistakeCard mistake={makeMistake({ reviews: makeLadder(2) })} />);

    expect(screen.getByText("due now")).toBeInTheDocument();
  });

  it("counts down to the next rung when nothing is due", () => {
    render(<MistakeCard mistake={makeMistake()} />);

    expect(screen.getByText(/^in /)).toBeInTheDocument();
  });

  it("says a hand-logged question is waiting, not that it is being analysed", () => {
    // "analysing…" on a question nobody asked the AI about is a lie about state.
    render(
      <MistakeCard
        mistake={makeMistake({
          analysis_status: "not_requested",
          error_type: null,
          topic: null,
          urgency: null,
        })}
      />,
    );

    expect(screen.getByText("no debrief yet")).toBeInTheDocument();
    expect(screen.queryByText("analysing…")).not.toBeInTheDocument();
  });

  it("does not claim a slot while the analysis is still running", () => {
    render(
      <MistakeCard
        mistake={makeMistake({ analysis_status: "pending", error_type: null, topic: null })}
      />,
    );

    expect(screen.getByText("analysing…")).toBeInTheDocument();
  });
});
