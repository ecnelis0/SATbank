import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import { ReviewSession } from "@/components/app/review-session";
import { makeDueReview } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

describe("ReviewSession", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("withholds the answer until the student asks for it", async () => {
    const due = makeDueReview();
    vi.spyOn(api, "dueReviews").mockResolvedValue([due]);
    const user = userEvent.setup();

    renderWithQuery(<ReviewSession />);
    await screen.findByText(due.mistake.question_text);

    // The whole point of a review is answering first: the correct answer and the
    // analysis must not be on screen yet.
    expect(screen.queryByText(/The answer is/)).not.toBeInTheDocument();
    expect(screen.queryByText(due.mistake.why_wrong!)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Show the answer" }));

    expect(await screen.findByText(/The answer is/)).toBeInTheDocument();
    expect(screen.getByText(due.mistake.why_wrong!)).toBeInTheDocument();
  });

  it("reports a repeat miss as 'wrong' so the backend restarts the ladder", async () => {
    const due = makeDueReview();
    vi.spyOn(api, "dueReviews").mockResolvedValue([due]);
    const complete = vi.spyOn(api, "completeReview").mockResolvedValue({
      review: { ...due.review, completed_at: new Date().toISOString(), outcome: "wrong" },
      ladder_restarted: true,
      next_due_at: new Date(Date.now() + 3600_000).toISOString(),
    });
    const user = userEvent.setup();

    renderWithQuery(<ReviewSession />);
    await screen.findByText(due.mistake.question_text);
    await user.click(screen.getByRole("button", { name: "Show the answer" }));
    await user.click(await screen.findByRole("button", { name: "Missed it again" }));

    await waitFor(() => expect(complete).toHaveBeenCalledWith(due.review.id, "wrong"));
  });

  it("reports success as 'correct'", async () => {
    const due = makeDueReview();
    vi.spyOn(api, "dueReviews").mockResolvedValue([due]);
    const complete = vi.spyOn(api, "completeReview").mockResolvedValue({
      review: { ...due.review, completed_at: new Date().toISOString(), outcome: "correct" },
      ladder_restarted: false,
      next_due_at: new Date(Date.now() + 86_400_000).toISOString(),
    });
    const user = userEvent.setup();

    renderWithQuery(<ReviewSession />);
    await screen.findByText(due.mistake.question_text);
    await user.click(screen.getByRole("button", { name: "Show the answer" }));
    await user.click(await screen.findByRole("button", { name: "I got it" }));

    await waitFor(() => expect(complete).toHaveBeenCalledWith(due.review.id, "correct"));
  });

  it("says so when nothing is due, rather than showing an empty card", async () => {
    vi.spyOn(api, "dueReviews").mockResolvedValue([]);

    renderWithQuery(<ReviewSession />);

    expect(await screen.findByText("Nothing is due.")).toBeInTheDocument();
  });

  it("names which rung of the ladder this review is", async () => {
    const due = makeDueReview();
    vi.spyOn(api, "dueReviews").mockResolvedValue([due]);

    renderWithQuery(<ReviewSession />);

    expect(await screen.findByText(/1 hour review/)).toBeInTheDocument();
  });
});
