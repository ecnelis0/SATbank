import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MistakeLabels } from "@/components/app/mistake-labels";
import { api } from "@/lib/api";
import { makeMistake } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

describe("MistakeLabels", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("adds a label to a question already in the bank", async () => {
    vi.spyOn(api, "listTags").mockResolvedValue([]);
    const update = vi.spyOn(api, "updateMistake").mockResolvedValue(makeMistake());
    const mistake = makeMistake({ tags: [] });
    const user = userEvent.setup();

    renderWithQuery(<MistakeLabels mistake={mistake} editable />);
    await user.type(screen.getByLabelText("Add a label"), "forgot the +C{Enter}");

    await waitFor(() =>
      expect(update).toHaveBeenCalledWith(mistake.id, { tags: ["forgot the +C"] }),
    );
  });

  it("keeps the labels already on the question", async () => {
    vi.spyOn(api, "listTags").mockResolvedValue([]);
    const update = vi.spyOn(api, "updateMistake").mockResolvedValue(makeMistake());
    const mistake = makeMistake({ tags: ["by mistake"] });
    const user = userEvent.setup();

    renderWithQuery(<MistakeLabels mistake={mistake} editable />);
    await user.type(screen.getByLabelText("Add a label"), "guessed{Enter}");

    await waitFor(() =>
      expect(update).toHaveBeenCalledWith(mistake.id, {
        tags: ["by mistake", "guessed"],
      }),
    );
  });

  it("removes one", async () => {
    vi.spyOn(api, "listTags").mockResolvedValue([]);
    const update = vi.spyOn(api, "updateMistake").mockResolvedValue(makeMistake());
    const mistake = makeMistake({ tags: ["by mistake", "guessed"] });
    const user = userEvent.setup();

    renderWithQuery(<MistakeLabels mistake={mistake} editable />);
    await user.click(screen.getByRole("button", { name: "Remove label by mistake" }));

    await waitFor(() =>
      expect(update).toHaveBeenCalledWith(mistake.id, { tags: ["guessed"] }),
    );
  });

  it("offers labels used elsewhere in the bank", async () => {
    vi.spyOn(api, "listTags").mockResolvedValue([
      { tag: "ran out of time", count: 3, suggested: false },
    ]);

    renderWithQuery(<MistakeLabels mistake={makeMistake({ tags: [] })} editable />);

    expect(
      await screen.findByRole("button", { name: /ran out of time/ }),
    ).toBeInTheDocument();
  });

  it("shows labels read-only where the question is not being edited", () => {
    renderWithQuery(<MistakeLabels mistake={makeMistake({ tags: ["guessed"] })} />);

    expect(screen.getByText("guessed")).toBeInTheDocument();
    expect(screen.queryByLabelText("Add a label")).not.toBeInTheDocument();
  });
});
