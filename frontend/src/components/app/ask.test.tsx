import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Ask } from "@/components/app/ask";
import { api } from "@/lib/api";
import { makeMistake } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";
import type { Answer, BankQuery } from "@/lib/types";

const EMPTY_QUERY: BankQuery = {
  concept_ids: [],
  concepts: [],
  tags: [],
  has_concept: null,
  urgency: [],
  error_type: [],
  section: [],
  topics: [],
  text: null,
  logged_after: null,
  logged_before: null,
  only_due: false,
  sort: "newest",
  limit: 25,
};

function answer(overrides: Partial<Answer> = {}): Answer {
  return {
    question: "everything",
    answer: "1 question matched.",
    analyzer: "claude",
    analyzer_ready: true,
    filter_description: "everything in the bank",
    query: EMPTY_QUERY,
    mistakes: [makeMistake()],
    error: null,
    ...overrides,
  };
}

describe("Ask", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("sends the question the student typed", async () => {
    const ask = vi.spyOn(api, "ask").mockResolvedValue(answer());
    const user = userEvent.setup();

    renderWithQuery(<Ask />);
    const question =
      "give me all the questions logged in the past 3 months that are very important and from the reading category";
    await user.type(screen.getByLabelText("Ask about your bank"), question);
    await user.click(screen.getByRole("button", { name: "Ask" }));

    await waitFor(() => expect(ask).toHaveBeenCalledWith(question));
  });

  it("shows the matching questions, not just the prose", async () => {
    const mistake = makeMistake();
    vi.spyOn(api, "ask").mockResolvedValue(
      answer({ answer: "One very important Reading miss.", mistakes: [mistake] }),
    );
    const user = userEvent.setup();

    renderWithQuery(<Ask />);
    await user.type(screen.getByLabelText("Ask about your bank"), "very important reading");
    await user.click(screen.getByRole("button", { name: "Ask" }));

    expect(await screen.findByText("One very important Reading miss.")).toBeInTheDocument();
    // Matched by text rather than a regex built from it: the question contains "+".
    const hit = screen.getByRole("link");
    expect(hit).toHaveAttribute("href", `/bank/${mistake.id}`);
    expect(within(hit).getByText(mistake.question_text)).toBeInTheDocument();
  });

  it("shows what was actually searched, so a misread sentence is visible", async () => {
    vi.spyOn(api, "ask").mockResolvedValue(
      answer({
        filter_description: "very important, Reading & Writing, logged since 2026-06-09",
        mistakes: [],
      }),
    );
    const user = userEvent.setup();

    renderWithQuery(<Ask />);
    await user.type(screen.getByLabelText("Ask about your bank"), "very important reading");
    await user.click(screen.getByRole("button", { name: "Ask" }));

    expect(
      await screen.findByText(/Searched: very important, Reading & Writing, logged since/),
    ).toBeInTheDocument();
    // An empty result must not read as "you have nothing to review".
    expect(screen.getByText("Nothing matched. Try a looser question.")).toBeInTheDocument();
  });

  it("the example questions are one click, not something to retype", async () => {
    const ask = vi.spyOn(api, "ask").mockResolvedValue(answer());
    const user = userEvent.setup();

    renderWithQuery(<Ask />);
    await user.click(screen.getByRole("button", { name: /past 3 months/ }));

    await waitFor(() =>
      expect(ask).toHaveBeenCalledWith(
        "Everything very important from Reading in the past 3 months",
      ),
    );
  });

  it("will not send an empty question", async () => {
    const ask = vi.spyOn(api, "ask");
    const user = userEvent.setup();

    renderWithQuery(<Ask />);
    await user.type(screen.getByLabelText("Ask about your bank"), "   ");

    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
    expect(ask).not.toHaveBeenCalled();
  });

  it("still lists the rows when the model failed to summarise them", async () => {
    vi.spyOn(api, "ask").mockResolvedValue(
      answer({ answer: "1 question(s) matched.", error: "RuntimeError: provider is down" }),
    );
    const user = userEvent.setup();

    renderWithQuery(<Ask />);
    await user.type(screen.getByLabelText("Ask about your bank"), "everything");
    await user.click(screen.getByRole("button", { name: "Ask" }));

    expect(await screen.findByText("1 question(s) matched.")).toBeInTheDocument();
    expect(screen.getByText(/provider is down/)).toBeInTheDocument();
    expect(screen.getAllByRole("link")).toHaveLength(1);
  });

  it("says when the offline assistant answered, so it is not mistaken for a search", async () => {
    vi.spyOn(api, "ask").mockResolvedValue(
      answer({ analyzer: "stub", analyzer_ready: true }),
    );
    const user = userEvent.setup();

    renderWithQuery(<Ask />);
    await user.type(screen.getByLabelText("Ask about your bank"), "everything");
    await user.click(screen.getByRole("button", { name: "Ask" }));

    expect(await screen.findByText(/Offline assistant/)).toBeInTheDocument();
  });

  it("says plainly when a provider is selected but its key is missing", async () => {
    vi.spyOn(api, "ask").mockResolvedValue(
      answer({ analyzer: "claude", analyzer_ready: false }),
    );
    const user = userEvent.setup();

    renderWithQuery(<Ask />);
    await user.type(screen.getByLabelText("Ask about your bank"), "everything");
    await user.click(screen.getByRole("button", { name: "Ask" }));

    expect(await screen.findByText(/API key is missing/)).toBeInTheDocument();
  });

  it("shows no offline warning once a real analyzer is answering", async () => {
    vi.spyOn(api, "ask").mockResolvedValue(answer({ analyzer: "claude" }));
    const user = userEvent.setup();

    renderWithQuery(<Ask />);
    await user.type(screen.getByLabelText("Ask about your bank"), "everything");
    await user.click(screen.getByRole("button", { name: "Ask" }));

    await screen.findByText("1 question matched.");
    expect(screen.queryByText(/Offline assistant/)).not.toBeInTheDocument();
  });

  it("reports a failed request instead of showing a stale answer", async () => {
    vi.spyOn(api, "ask").mockRejectedValue(new Error("Failed to fetch"));
    const user = userEvent.setup();

    renderWithQuery(<Ask />);
    await user.type(screen.getByLabelText("Ask about your bank"), "everything");
    await user.click(screen.getByRole("button", { name: "Ask" }));

    expect(await screen.findByText("Failed to fetch")).toBeInTheDocument();
  });
});

describe("Ask keyboard", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("sends on Enter and keeps Shift+Enter for a new line", async () => {
    const ask = vi.spyOn(api, "ask").mockResolvedValue(answer());
    const user = userEvent.setup();

    renderWithQuery(<Ask />);
    const box = screen.getByLabelText("Ask about your bank");
    await user.type(box, "line one{Shift>}{Enter}{/Shift}line two");
    expect(ask).not.toHaveBeenCalled();

    await user.type(box, "{Enter}");
    await waitFor(() => expect(ask).toHaveBeenCalledWith("line one\nline two"));
  });
});

describe("Ask results", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("labels each hit with its urgency and slot", async () => {
    vi.spyOn(api, "ask").mockResolvedValue(
      answer({ mistakes: [makeMistake({ urgency: "fundamental" })] }),
    );
    const user = userEvent.setup();

    renderWithQuery(<Ask />);
    await user.click(screen.getByRole("button", { name: /due for review now/ }));

    const hit = await screen.findByRole("link");
    expect(within(hit).getByText("Fundamental concept")).toBeInTheDocument();
    expect(within(hit).getByText(/Careless arithmetic/)).toBeInTheDocument();
  });

  it("debriefs each group and lists the questions lost to it", async () => {
    const user = userEvent.setup();
    const q1 = makeMistake({ id: "q1", question_text: "Solve 3x + 7 = 22" });
    const q2 = makeMistake({ id: "q2", question_text: "Solve 5x - 1 = 9" });
    const q3 = makeMistake({ id: "q3", question_text: "Which choice best supports the claim?" });
    vi.spyOn(api, "ask").mockResolvedValue(
      answer({
        answer: "Concept gaps cost you the most.",
        mistakes: [q1, q2, q3],
        groups: [
          {
            key: "reason:concept_gap",
            kind: "reason",
            label: "Concept gap",
            count: 2,
            repeat_misses: 1,
            why: "You isolate x before undoing the constant.",
            what_to_do: "Undo the + and - first.",
            mistakes: [q1, q2],
          },
          {
            key: "reason:trap_answer",
            kind: "reason",
            label: "Walked into the trap",
            count: 1,
            repeat_misses: 0,
            why: null,
            what_to_do: null,
            mistakes: [q3],
          },
        ],
      }),
    );
    renderWithQuery(<Ask />);

    await user.type(screen.getByLabelText("Ask about your bank"), "Where am I losing points?");
    await user.click(screen.getByRole("button", { name: "Ask" }));

    const gap = await screen.findByRole("region", { name: "Concept gap" });
    expect(within(gap).getByText("You isolate x before undoing the constant.")).toBeInTheDocument();
    expect(within(gap).getByText("Undo the + and - first.")).toBeInTheDocument();
    expect(within(gap).getByText(/2 questions · missed again 1×/)).toBeInTheDocument();
    expect(within(gap).getAllByRole("link").map((a) => a.getAttribute("href"))).toEqual([
      "/bank/q1",
      "/bank/q2",
    ]);
    // A group the model said nothing about still lists its question.
    const trap = screen.getByRole("region", { name: "Walked into the trap" });
    expect(within(trap).getByRole("link")).toHaveAttribute("href", "/bank/q3");
  });

  it("keeps the flat list when the answer is not a breakdown", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "ask").mockResolvedValue(answer({ groups: [] }));
    renderWithQuery(<Ask />);

    await user.type(screen.getByLabelText("Ask about your bank"), "What is due?");
    await user.click(screen.getByRole("button", { name: "Ask" }));

    await screen.findByText("1 question matched.");
    expect(screen.queryByRole("region")).not.toBeInTheDocument();
    expect(screen.getAllByRole("link")).toHaveLength(1);
  });
});
