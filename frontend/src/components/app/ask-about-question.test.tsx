import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AskAboutQuestion } from "@/components/app/ask-about-question";
import { api } from "@/lib/api";
import { makeMistake } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";

const reply = (answer: string) => ({
  answer,
  analyzer: "claude",
  analyzer_ready: true,
  error: null,
});

describe("AskAboutQuestion", () => {
  it("offers the opener the panel exists for", () => {
    renderWithQuery(<AskAboutQuestion mistake={makeMistake()} />);
    expect(
      screen.getByRole("button", { name: "What does this debrief mean?" }),
    ).toBeInTheDocument();
  });

  it("shows what was asked and what came back", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "askAboutMistake").mockResolvedValue(
      reply("A takeaway is the rule to remember."),
    );
    renderWithQuery(<AskAboutQuestion mistake={makeMistake()} />);

    await user.type(
      screen.getByLabelText("Ask about this question"),
      "What does takeaway mean?",
    );
    await user.click(screen.getByRole("button", { name: "Ask" }));

    expect(await screen.findByText("What does takeaway mean?")).toBeInTheDocument();
    expect(
      await screen.findByText("A takeaway is the rule to remember."),
    ).toBeInTheDocument();
  });

  it("sends the thread so far, and does not send the new question twice", async () => {
    // The API appends the new question itself. Including it in `history` too
    // makes the model answer something it has already been asked.
    const user = userEvent.setup();
    const ask = vi
      .spyOn(api, "askAboutMistake")
      .mockResolvedValue(reply("Because you stopped a step early."));
    renderWithQuery(<AskAboutQuestion mistake={makeMistake({ id: "q1" })} />);

    await user.click(screen.getByRole("button", { name: "Why is my answer wrong?" }));
    await screen.findByText("Because you stopped a step early.");

    await user.type(screen.getByLabelText("Ask about this question"), "And next time?");
    await user.click(screen.getByRole("button", { name: "Ask" }));

    await waitFor(() => expect(ask).toHaveBeenCalledTimes(2));
    expect(ask).toHaveBeenNthCalledWith(1, "q1", "Why is my answer wrong?", []);
    expect(ask).toHaveBeenNthCalledWith(2, "q1", "And next time?", [
      { role: "student", text: "Why is my answer wrong?" },
      { role: "assistant", text: "Because you stopped a step early." },
    ]);
  });

  it("says so in the thread when the request fails, rather than losing the question", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "askAboutMistake").mockRejectedValue(new Error("Can't reach the API"));
    renderWithQuery(<AskAboutQuestion mistake={makeMistake()} />);

    await user.click(screen.getByRole("button", { name: "Why is my answer wrong?" }));

    expect(await screen.findByText(/Can't reach the API/)).toBeInTheDocument();
    // What they asked is still on screen.
    expect(screen.getByText("Why is my answer wrong?")).toBeInTheDocument();
  });

  it("will not send an empty question", async () => {
    const ask = vi.spyOn(api, "askAboutMistake");
    renderWithQuery(<AskAboutQuestion mistake={makeMistake()} />);
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
    expect(ask).not.toHaveBeenCalled();
  });

  it("starts again on request", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "askAboutMistake").mockResolvedValue(reply("An answer."));
    renderWithQuery(<AskAboutQuestion mistake={makeMistake()} />);

    await user.click(screen.getByRole("button", { name: "Why is my answer wrong?" }));
    await screen.findByText("An answer.");

    await user.click(screen.getByRole("button", { name: "Start again" }));

    expect(screen.queryByText("An answer.")).not.toBeInTheDocument();
    // And the openers are back, because the thread is empty again.
    expect(
      screen.getByRole("button", { name: "What does this debrief mean?" }),
    ).toBeInTheDocument();
  });
});
