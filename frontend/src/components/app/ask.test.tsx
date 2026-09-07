import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Ask } from "@/components/app/ask";
import { api } from "@/lib/api";
import { makeMistake } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";
import type { Answer, BankQuery } from "@/lib/types";

const EMPTY_QUERY: BankQuery = {
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
});
