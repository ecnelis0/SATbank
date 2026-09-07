import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConceptTags } from "@/components/app/concept-tags";
import { api } from "@/lib/api";
import type { Concept, ConceptDetail } from "@/lib/types";
import { makeMistake } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

const CONCEPTS: Concept[] = [
  {
    id: "c1",
    title: "Circumference gives you the radius first",
    body: null,
    section: "math",
    created_at: new Date().toISOString(),
    updated_at: null,
    question_count: 2,
    images: [],
  },
  {
    id: "c2",
    title: "Read the stem twice",
    body: null,
    section: null,
    created_at: new Date().toISOString(),
    updated_at: null,
    question_count: 0,
    images: [],
  },
];

const detail = (): ConceptDetail => ({ ...CONCEPTS[0], mistakes: [] });

describe("ConceptTags", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("says plainly when a question is filed under nothing", () => {
    renderWithQuery(<ConceptTags mistake={makeMistake()} />);

    expect(screen.getByText("Not filed under any concept yet.")).toBeInTheDocument();
  });

  it("tags an existing question with a concept", async () => {
    vi.spyOn(api, "listConcepts").mockResolvedValue(CONCEPTS);
    const tag = vi.spyOn(api, "tagQuestion").mockResolvedValue(detail());
    const mistake = makeMistake();
    const user = userEvent.setup();

    renderWithQuery(<ConceptTags mistake={mistake} />);
    await user.click(screen.getByRole("button", { name: "Tag with a concept" }));
    await user.click(await screen.findByRole("button", { name: CONCEPTS[0].title }));

    await waitFor(() => expect(tag).toHaveBeenCalledWith("c1", mistake.id));
  });

  it("does not offer a concept the question already carries", async () => {
    vi.spyOn(api, "listConcepts").mockResolvedValue(CONCEPTS);
    const user = userEvent.setup();

    renderWithQuery(
      <ConceptTags
        mistake={makeMistake({ concepts: [{ id: "c1", title: CONCEPTS[0].title }] })}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Tag with a concept" }));

    // Offered once as a removable tag, never again as something to add.
    expect(
      await screen.findByRole("button", { name: CONCEPTS[1].title }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: CONCEPTS[0].title }),
    ).not.toBeInTheDocument();
  });

  it("shows each tag as a link to the concept, and can remove it", async () => {
    const untag = vi.spyOn(api, "untagQuestion").mockResolvedValue(detail());
    const mistake = makeMistake({ concepts: [{ id: "c1", title: CONCEPTS[0].title }] });
    const user = userEvent.setup();

    renderWithQuery(<ConceptTags mistake={mistake} />);

    expect(screen.getByRole("link", { name: CONCEPTS[0].title })).toHaveAttribute(
      "href",
      "/concepts/c1",
    );

    await user.click(screen.getByRole("button", { name: `Remove ${CONCEPTS[0].title}` }));
    await waitFor(() => expect(untag).toHaveBeenCalledWith("c1", mistake.id));
  });

  it("points at writing one when there are no concepts yet", async () => {
    vi.spyOn(api, "listConcepts").mockResolvedValue([]);
    const user = userEvent.setup();

    renderWithQuery(<ConceptTags mistake={makeMistake()} />);
    await user.click(screen.getByRole("button", { name: "Tag with a concept" }));

    expect(await screen.findByText(/No concepts written yet/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Write one" })).toHaveAttribute(
      "href",
      "/concepts",
    );
  });

  it("does not fetch the concept list until it is needed", async () => {
    const list = vi.spyOn(api, "listConcepts").mockResolvedValue(CONCEPTS);

    renderWithQuery(<ConceptTags mistake={makeMistake()} />);

    expect(list).not.toHaveBeenCalled();
  });
});
