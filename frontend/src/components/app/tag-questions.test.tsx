import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TagQuestions } from "@/components/app/tag-questions";
import { api } from "@/lib/api";
import type { ConceptDetail } from "@/lib/types";
import { makeMistake } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

const IN_BANK = [
  makeMistake({ id: "m1", question_text: "If 3x + 7 = 22, what is x?" }),
  makeMistake({ id: "m2", question_text: "A circle has circumference 12π." }),
];

function concept(mistakes: ConceptDetail["mistakes"] = []): ConceptDetail {
  return {
    id: "c1",
    title: "Circumference gives the radius",
    body: null,
    section: "math",
    created_at: new Date().toISOString(),
    updated_at: null,
    question_count: mistakes.length,
    images: [],
    mistakes,
  };
}

describe("TagQuestions", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("tags a question onto the concept from the concept's own page", async () => {
    vi.spyOn(api, "listMistakes").mockResolvedValue(IN_BANK);
    const tag = vi.spyOn(api, "tagQuestion").mockResolvedValue(concept([IN_BANK[0]]));
    const user = userEvent.setup();

    renderWithQuery(<TagQuestions concept={concept()} />);
    await user.click(
      screen.getByRole("button", { name: "Tag questions with this concept" }),
    );
    await user.click(await screen.findByRole("button", { name: /3x \+ 7/ }));

    await waitFor(() => expect(tag).toHaveBeenCalledWith("c1", "m1"));
  });

  it("does not offer a question the concept already carries", async () => {
    vi.spyOn(api, "listMistakes").mockResolvedValue(IN_BANK);
    const user = userEvent.setup();

    renderWithQuery(<TagQuestions concept={concept([IN_BANK[0]])} />);
    await user.click(
      screen.getByRole("button", { name: "Tag questions with this concept" }),
    );

    expect(await screen.findByRole("button", { name: /circumference 12/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /3x \+ 7/ })).not.toBeInTheDocument();
  });

  it("searches the bank rather than making you scroll it", async () => {
    const list = vi.spyOn(api, "listMistakes").mockResolvedValue(IN_BANK);
    const user = userEvent.setup();

    renderWithQuery(<TagQuestions concept={concept()} />);
    await user.click(
      screen.getByRole("button", { name: "Tag questions with this concept" }),
    );
    await user.type(await screen.findByLabelText("Search your questions"), "circle");

    await waitFor(() => expect(list).toHaveBeenCalledWith({ q: "circle" }));
  });

  it("says so when everything matching is already tagged", async () => {
    vi.spyOn(api, "listMistakes").mockResolvedValue([IN_BANK[0]]);
    const user = userEvent.setup();

    renderWithQuery(<TagQuestions concept={concept([IN_BANK[0]])} />);
    await user.click(
      screen.getByRole("button", { name: "Tag questions with this concept" }),
    );

    expect(
      await screen.findByText("Every question matching that is already tagged."),
    ).toBeInTheDocument();
  });

  it("does not fetch the bank until the picker is opened", () => {
    const list = vi.spyOn(api, "listMistakes");

    renderWithQuery(<TagQuestions concept={concept()} />);

    expect(list).not.toHaveBeenCalled();
  });
});
