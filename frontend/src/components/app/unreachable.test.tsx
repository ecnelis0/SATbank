import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Categories } from "@/components/app/categories";
import { ReviewSession } from "@/components/app/review-session";
import { Unreachable } from "@/components/app/unreachable";
import { api } from "@/lib/api";
import { renderWithQuery } from "@/test/render";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

const down = () => new Error("Failed to fetch");

describe("Unreachable", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("says nothing has been lost, because that is the fear", () => {
    renderWithQuery(<Unreachable error={down()} />);

    expect(screen.getByRole("alert")).toHaveTextContent(/Can’t reach the app’s API/);
    expect(screen.getByRole("alert")).toHaveTextContent(/Nothing has been lost/);
    expect(screen.getByRole("alert")).toHaveTextContent(/Failed to fetch/);
  });

  it("offers a retry", async () => {
    const user = userEvent.setup();
    const { client } = renderWithQuery(<Unreachable />);
    const invalidate = vi.spyOn(client, "invalidateQueries");

    await user.click(screen.getByRole("button", { name: "Try again" }));

    expect(invalidate).toHaveBeenCalled();
  });
});

describe("a failed load is never shown as an empty bank", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("the review session does not claim nothing is due", async () => {
    vi.spyOn(api, "dueReviews").mockRejectedValue(down());

    renderWithQuery(<ReviewSession />);

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/Can’t reach/),
    );
    // The one message that would make a student close the app believing they were
    // up to date.
    expect(screen.queryByText("Nothing is due.")).not.toBeInTheDocument();
  });

  it("the category rail does not render a bank with no categories", async () => {
    vi.spyOn(api, "stats").mockRejectedValue(down());
    vi.spyOn(api, "listConcepts").mockResolvedValue([]);

    renderWithQuery(<Categories />);

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/Can’t reach/),
    );
    expect(screen.queryByText("How urgent")).not.toBeInTheDocument();
  });

  it("still shows the real empty state when the API answers with nothing", async () => {
    vi.spyOn(api, "dueReviews").mockResolvedValue([]);

    renderWithQuery(<ReviewSession />);

    expect(await screen.findByText("Nothing is due.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
