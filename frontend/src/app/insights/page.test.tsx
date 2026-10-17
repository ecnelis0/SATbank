import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import InsightsPage from "@/app/insights/page";
import { api } from "@/lib/api";
import type { Insight } from "@/lib/types";
import { makeMistake } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}));

function insight(overrides: Partial<Insight> = {}): Insight {
  return {
    id: "i1",
    created_at: "2026-10-17T10:00:00Z",
    focus: null,
    analyzer: "agent",
    question_count: 2,
    stats: {
      questions: 2,
      debriefed: 2,
      talked_to: 1,
      reviews_right: 3,
      reviews_wrong: 1,
      by_reason: [{ label: "Misread the question", count: 2 }],
      by_section: [{ label: "Math", count: 2 }],
      top_patterns: [],
    },
    report: {
      answer: "",
      overview: "You rush the last step.",
      doing_well: [{ title: "Honest notes", detail: "You say what happened.", question_ids: [] }],
      going_wrong: [
        { title: "Answering a different quantity", detail: "Twice.", question_ids: ["q1"] },
      ],
      next_steps: ["Circle what the question asks for."],
    },
    ...overrides,
  };
}

afterEach(() => vi.restoreAllMocks());

describe("InsightsPage", () => {
  it("shows the latest analysis, with links to the questions behind each point", async () => {
    vi.spyOn(api, "listInsights").mockResolvedValue([insight()]);
    vi.spyOn(api, "listMistakes").mockResolvedValue([
      makeMistake({ id: "q1", question_text: "If 3x + 7 = 22, what is x?" }),
    ]);
    renderWithQuery(<InsightsPage />);

    expect(await screen.findByText("You rush the last step.")).toBeInTheDocument();
    expect(screen.getByText("Honest notes")).toBeInTheDocument();
    const link = await screen.findByRole("link", { name: "If 3x + 7 = 22, what is x?" });
    expect(link).toHaveAttribute("href", "/bank/q1");
    expect(screen.getByText("Circle what the question asks for.")).toBeInTheDocument();
    // The database's count, shown as a number beside the prose.
    const stats = screen.getByText("Right on review").closest("div")!;
    expect(within(stats).getByText("3")).toBeInTheDocument();
  });

  it("writes a new one with the focus given, and shows it first", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "listInsights").mockResolvedValue([insight()]);
    vi.spyOn(api, "listMistakes").mockResolvedValue([]);
    const write = vi.spyOn(api, "newInsight").mockResolvedValue(
      insight({
        id: "i2",
        focus: "Why grammar?",
        report: { ...insight().report, answer: "Comma splices, mostly.", overview: "New." },
      }),
    );
    renderWithQuery(<InsightsPage />);

    await screen.findByText("You rush the last step.");
    await user.type(screen.getByLabelText("What to look at"), "Why grammar?");
    await user.click(screen.getByRole("button", { name: "Analyse my bank" }));

    expect(write).toHaveBeenCalledWith("Why grammar?");
    expect(await screen.findByText("Comma splices, mostly.")).toBeInTheDocument();
    expect(screen.queryByText("You rush the last step.")).not.toBeInTheDocument();
  });

  it("can go back to an earlier analysis", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "listInsights").mockResolvedValue([
      insight({ id: "new", report: { ...insight().report, overview: "This week." } }),
      insight({
        id: "old",
        created_at: "2026-09-01T10:00:00Z",
        report: { ...insight().report, overview: "Last month." },
      }),
    ]);
    vi.spyOn(api, "listMistakes").mockResolvedValue([]);
    renderWithQuery(<InsightsPage />);

    await screen.findByText("This week.");
    await user.click(screen.getByRole("button", { name: /1 Sep 2026/ }));
    expect(await screen.findByText("Last month.")).toBeInTheDocument();
  });

  it("says the API is unreachable rather than that there is nothing", async () => {
    vi.spyOn(api, "listInsights").mockRejectedValue(new Error("Failed to fetch"));
    vi.spyOn(api, "listMistakes").mockResolvedValue([]);
    renderWithQuery(<InsightsPage />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByText("No analysis yet.")).not.toBeInTheDocument();
  });

  it("explains an empty history", async () => {
    vi.spyOn(api, "listInsights").mockResolvedValue([]);
    vi.spyOn(api, "listMistakes").mockResolvedValue([]);
    renderWithQuery(<InsightsPage />);
    await waitFor(() => expect(screen.getByText("No analysis yet.")).toBeInTheDocument());
  });
});
