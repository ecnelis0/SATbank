import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConceptHeader } from "@/components/app/concept-header";
import { api } from "@/lib/api";
import type { ConceptDetail } from "@/lib/types";
import { renderWithQuery } from "@/test/render";

function concept(overrides: Partial<ConceptDetail> = {}): ConceptDetail {
  return {
    id: "c1",
    title: "Circumference gives you the radius first",
    body: "C = 2πr, so r = C / 2π.",
    section: "math",
    created_at: new Date().toISOString(),
    updated_at: null,
    question_count: 3,
    images: [],
    mistakes: [],
    ...overrides,
  };
}

describe("ConceptHeader", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("shows the concept itself, which filtering by it used to hide", async () => {
    vi.spyOn(api, "getConcept").mockResolvedValue(concept());

    renderWithQuery(<ConceptHeader conceptId="c1" />);

    expect(
      await screen.findByText("Circumference gives you the radius first"),
    ).toBeInTheDocument();
    expect(screen.getByText("C = 2πr, so r = C / 2π.")).toBeInTheDocument();
    expect(screen.getByText("Math")).toBeInTheDocument();
    expect(screen.getByText(/3 questions filed under this concept/)).toBeInTheDocument();
  });

  it("shows the concept's diagrams", async () => {
    vi.spyOn(api, "getConcept").mockResolvedValue(
      concept({
        images: [
          {
            id: "i1",
            url: "/uploads/a.png",
            content_type: "image/png",
            byte_size: 10,
            width: 100,
            height: 80,
            caption: null,
            position: 0,
          },
        ],
      }),
    );

    renderWithQuery(<ConceptHeader conceptId="c1" />);

    expect(
      await screen.findByRole("img", { name: "Diagram 1 of the concept" }),
    ).toBeInTheDocument();
  });

  it("links through to the full concept page", async () => {
    vi.spyOn(api, "getConcept").mockResolvedValue(concept());

    renderWithQuery(<ConceptHeader conceptId="c1" />);

    expect(await screen.findByRole("link", { name: /Open concept/ })).toHaveAttribute(
      "href",
      "/concepts/c1",
    );
  });

  it("says one question, not one questions", async () => {
    vi.spyOn(api, "getConcept").mockResolvedValue(concept({ question_count: 1 }));

    renderWithQuery(<ConceptHeader conceptId="c1" />);

    expect(
      await screen.findByText(/1 question filed under this concept/),
    ).toBeInTheDocument();
  });
});
