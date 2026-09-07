import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MistakeCard } from "@/components/app/mistake-card";
import { makeLadder, makeMistake } from "@/test/fixtures";

describe("MistakeCard", () => {
  it("shows the slot the AI filed this under", () => {
    render(<MistakeCard mistake={makeMistake()} />);

    expect(screen.getByText("Careless arithmetic")).toBeInTheDocument();
    expect(screen.getByText("linear equations")).toBeInTheDocument();
  });

  it("says a review is due rather than counting down to it", () => {
    render(<MistakeCard mistake={makeMistake({ reviews: makeLadder(2) })} />);

    expect(screen.getByText("review due now")).toBeInTheDocument();
  });

  it("counts down to the next rung when nothing is due", () => {
    render(<MistakeCard mistake={makeMistake()} />);

    expect(screen.getByText(/next review in/)).toBeInTheDocument();
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
