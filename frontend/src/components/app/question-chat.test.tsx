import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AskAboutQuestion } from "@/components/app/ask-about-question";
import { DebriefChat } from "@/components/app/debrief-chat";
import { QuestionChatProvider } from "@/components/app/question-chat";
import { api } from "@/lib/api";
import type { DebriefTurn } from "@/lib/types";
import { makeMistake } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}));

const reply = (answer: string) => ({
  answer,
  analyzer: "claude",
  analyzer_ready: true,
  error: null,
});

function turn(role: DebriefTurn["role"], text: string): DebriefTurn {
  return { id: text, role, text, created_at: "2026-10-17T10:00:00Z", analyzer: null };
}

function Both() {
  const mistake = makeMistake({ id: "q1" });
  return (
    <QuestionChatProvider>
      <DebriefChat mistake={mistake} />
      <AskAboutQuestion mistake={mistake} />
    </QuestionChatProvider>
  );
}

afterEach(() => vi.restoreAllMocks());

describe("the two chats on a question", () => {
  it("sends what was worked out in the ask chat along with a message to the debrief", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "debriefConversation").mockResolvedValue([]);
    vi.spyOn(api, "askAboutMistake").mockResolvedValue(reply("You solved for 3x."));
    const talk = vi.spyOn(api, "talkToDebrief").mockResolvedValue({
      turns: [turn("assistant", "Re-filed as a misread.")],
      mistake: makeMistake({ id: "q1" }),
      error: null,
    });
    renderWithQuery(<Both />);

    await user.click(screen.getByRole("button", { name: "Why is my answer wrong?" }));
    await screen.findByText("You solved for 3x.");

    await user.type(screen.getByLabelText("Tell the debrief"), "Use what we just found.");
    await user.click(screen.getByRole("button", { name: "Send to the debrief" }));

    expect(talk).toHaveBeenCalledWith("q1", "Use what we just found.", [
      { role: "student", text: "Why is my answer wrong?" },
      { role: "assistant", text: "You solved for 3x." },
    ]);
    // And the ask chat hears what the debrief did with it.
    expect(
      await screen.findByText("From “Talk to the debrief”: Re-filed as a misread."),
    ).toBeInTheDocument();
  });

  it("does not send the same ask-chat turns to the debrief twice", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "debriefConversation").mockResolvedValue([]);
    vi.spyOn(api, "askAboutMistake").mockResolvedValue(reply("Because of the constant."));
    const talk = vi.spyOn(api, "talkToDebrief").mockResolvedValue({
      turns: [turn("assistant", "Noted.")],
      mistake: makeMistake({ id: "q1" }),
      error: null,
    });
    renderWithQuery(<Both />);

    await user.click(screen.getByRole("button", { name: "Why is my answer wrong?" }));
    await screen.findByText("Because of the constant.");
    await user.type(screen.getByLabelText("Tell the debrief"), "First.");
    await user.click(screen.getByRole("button", { name: "Send to the debrief" }));
    await screen.findByText("From “Talk to the debrief”: Noted.");

    await user.type(screen.getByLabelText("Tell the debrief"), "Second.");
    await user.click(screen.getByRole("button", { name: "Send to the debrief" }));

    await waitFor(() => expect(talk).toHaveBeenCalledTimes(2));
    expect(talk).toHaveBeenLastCalledWith("q1", "Second.", []);
  });

  it("a command in the ask chat shows up in the debrief's conversation", async () => {
    const user = userEvent.setup();
    const kept = vi
      .spyOn(api, "debriefConversation")
      .mockResolvedValueOnce([])
      .mockResolvedValue([
        turn("student", "Consider this in the debrief"),
        turn("assistant", "Done - re-filed."),
      ]);
    vi.spyOn(api, "askAboutMistake").mockResolvedValue({
      ...reply("Done - re-filed."),
      debrief_updated: true,
      mistake: makeMistake({ id: "q1" }),
    });
    renderWithQuery(<Both />);

    await user.type(
      screen.getByLabelText("Ask about this question"),
      "Consider this in the debrief",
    );
    await user.click(screen.getByRole("button", { name: "Ask" }));

    const conversation = await screen.findByRole("list", {
      name: "Conversation with the debrief",
    });
    await waitFor(() => expect(kept).toHaveBeenCalledTimes(2));
    expect(conversation).toHaveTextContent("Consider this in the debrief");
  });
});
