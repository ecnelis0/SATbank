import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DueHero } from "@/components/app/due-hero";

describe("DueHero", () => {
  it("leads with the number due, not the size of the bank", () => {
    render(<DueHero due={3} total={24} />);

    expect(screen.getByText("Due right now")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText(/ready to come back to you/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Start reviewing/ })).toHaveAttribute(
      "href",
      "/review",
    );
  });

  it("says one question, not one questions", () => {
    render(<DueHero due={1} total={10} />);

    expect(screen.getByText(/question is ready/)).toBeInTheDocument();
  });

  it("changes what it is about when nothing is due", () => {
    render(<DueHero due={0} total={12} />);

    expect(screen.getByText("Nothing due")).toBeInTheDocument();
    // No "start reviewing" call to action for a review that does not exist.
    expect(screen.queryByRole("link", { name: /Start reviewing/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Log a miss" })).toHaveAttribute("href", "/log");
    expect(screen.getByText("12")).toBeInTheDocument();
  });

  it("asks for the first question when the bank is empty", () => {
    render(<DueHero due={0} total={0} />);

    expect(screen.getByText(/Log the first one/)).toBeInTheDocument();
  });

  it("draws the whole ladder, labelled", () => {
    render(<DueHero due={2} total={9} />);

    const ladder = screen.getByRole("list", { name: "The review ladder" });
    expect(within(ladder).getAllByRole("listitem")).toHaveLength(5);
    expect(within(ladder).getByText("1 hour")).toBeInTheDocument();
    expect(within(ladder).getByText("1 month")).toBeInTheDocument();
  });
});
