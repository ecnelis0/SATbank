import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConceptForm } from "@/components/app/concept-form";
import { api } from "@/lib/api";
import type { Concept } from "@/lib/types";
import { renderWithQuery } from "@/test/render";

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

const saved = (section: Concept["section"] = "math"): Concept => ({
  id: "c1",
  title: "Inverse trig needs a domain",
  body: null,
  section,
  created_at: new Date().toISOString(),
  updated_at: null,
  question_count: 0,
  images: [],
});

describe("ConceptForm section", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("will not save until a section is chosen", async () => {
    const create = vi.spyOn(api, "createConcept").mockResolvedValue(saved());
    const user = userEvent.setup();

    renderWithQuery(<ConceptForm />);
    await user.type(screen.getByLabelText("The concept"), "Inverse trig needs a domain");

    // A title alone used to be enough, and the concept silently filed under nothing.
    expect(screen.getByRole("button", { name: "Add concept" })).toBeDisabled();
    expect(screen.getByText("Pick a section first.")).toBeInTheDocument();
    expect(create).not.toHaveBeenCalled();
  });

  it("saves the section that was chosen", async () => {
    const create = vi.spyOn(api, "createConcept").mockResolvedValue(saved());
    const user = userEvent.setup();

    renderWithQuery(<ConceptForm />);
    await user.type(screen.getByLabelText("The concept"), "Inverse trig needs a domain");
    await user.click(screen.getByRole("button", { name: "Math" }));
    await user.click(screen.getByRole("button", { name: "Add concept" }));

    await waitFor(() =>
      expect(create).toHaveBeenCalledWith(
        expect.objectContaining({ section: "math", title: "Inverse trig needs a domain" }),
      ),
    );
  });

  it("offers Reading & Writing too", async () => {
    const create = vi.spyOn(api, "createConcept").mockResolvedValue(saved("reading_writing"));
    const user = userEvent.setup();

    renderWithQuery(<ConceptForm />);
    await user.type(screen.getByLabelText("The concept"), "Evidence must be quoted");
    await user.click(screen.getByRole("button", { name: "Reading & Writing" }));
    await user.click(screen.getByRole("button", { name: "Add concept" }));

    await waitFor(() =>
      expect(create).toHaveBeenCalledWith(
        expect.objectContaining({ section: "reading_writing" }),
      ),
    );
  });

  it("keeps 'neither' available, but as a deliberate answer", async () => {
    const create = vi.spyOn(api, "createConcept").mockResolvedValue(saved(null));
    const user = userEvent.setup();

    renderWithQuery(<ConceptForm />);
    await user.type(screen.getByLabelText("The concept"), "Read the stem twice");
    await user.click(screen.getByRole("button", { name: "Neither" }));
    await user.click(screen.getByRole("button", { name: "Add concept" }));

    await waitFor(() =>
      expect(create).toHaveBeenCalledWith(expect.objectContaining({ section: null })),
    );
  });

  it("an existing concept opens on the section it already has", () => {
    renderWithQuery(<ConceptForm concept={saved("reading_writing")} />);

    expect(screen.getByRole("button", { name: "Reading & Writing" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "Save" })).not.toBeDisabled();
  });
});
