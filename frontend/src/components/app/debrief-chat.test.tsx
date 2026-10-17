import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DebriefChat } from "@/components/app/debrief-chat";
import { api, keys } from "@/lib/api";
import type { DebriefTurn, Mistake } from "@/lib/types";
import { makeMistake } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}));

function turn(role: DebriefTurn["role"], text: string, id = text): DebriefTurn {
  return { id, role, text, created_at: "2026-10-17T10:00:00Z", analyzer: null };
}

afterEach(() => vi.restoreAllMocks());

describe("DebriefChat", () => {
  it("shows the conversation already kept for this question", async () => {
    vi.spyOn(api, "debriefConversation").mockResolvedValue([
      turn("student", "I misread it."),
      turn("assistant", "Re-filed as a misread."),
    ]);
    renderWithQuery(<DebriefChat mistake={makeMistake()} />);

    expect(await screen.findByText("I misread it.")).toBeInTheDocument();
    expect(screen.getByText("Re-filed as a misread.")).toBeInTheDocument();
  });

  it("sends the message and puts the rewritten debrief where the page reads it", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "debriefConversation").mockResolvedValue([]);
    const rewritten: Mistake = makeMistake({
      id: "q1",
      error_type: "misread_question",
      headline: "You answered for 3x.",
    });
    const talk = vi.spyOn(api, "talkToDebrief").mockResolvedValue({
      turns: [turn("student", "I misread it."), turn("assistant", "Understood.")],
      mistake: rewritten,
      error: null,
    });
    const { client } = renderWithQuery(<DebriefChat mistake={makeMistake({ id: "q1" })} />);

    await user.type(screen.getByLabelText("Tell the debrief"), "I misread it.");
    await user.click(screen.getByRole("button", { name: "Send to the debrief" }));

    expect(talk).toHaveBeenCalledWith("q1", "I misread it.");
    expect(await screen.findByText("Understood.")).toBeInTheDocument();
    // The page's question query now holds the new debrief, so the panel above
    // re-renders with it rather than showing the old one until a refetch.
    expect(client.getQueryData<Mistake>(keys.mistake("q1"))?.error_type).toBe(
      "misread_question",
    );
  });

  it("keeps the message on screen while the rewrite is running", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "debriefConversation").mockResolvedValue([]);
    vi.spyOn(api, "talkToDebrief").mockReturnValue(new Promise(() => {}));
    renderWithQuery(<DebriefChat mistake={makeMistake()} />);

    await user.type(screen.getByLabelText("Tell the debrief"), "Shorter steps please");
    await user.click(screen.getByRole("button", { name: "Send to the debrief" }));

    expect(screen.getByText("Shorter steps please")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Rewriting the debrief");
  });

  it("says the message is saved when the model could not rewrite it", async () => {
    const { toast } = await import("sonner");
    const user = userEvent.setup();
    vi.spyOn(api, "debriefConversation").mockResolvedValue([]);
    vi.spyOn(api, "talkToDebrief").mockResolvedValue({
      turns: [turn("student", "Redo it")],
      mistake: makeMistake(),
      error: "AnalysisFailed: out of credit",
    });
    renderWithQuery(<DebriefChat mistake={makeMistake()} />);

    await user.type(screen.getByLabelText("Tell the debrief"), "Redo it");
    await user.click(screen.getByRole("button", { name: "Send to the debrief" }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(expect.stringMatching(/saved/)));
    expect(await screen.findByText("Redo it")).toBeInTheDocument();
  });

  it("gives the message back when it never reached the API", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "debriefConversation").mockResolvedValue([]);
    vi.spyOn(api, "talkToDebrief").mockRejectedValue(new Error("Can't reach the API"));
    renderWithQuery(<DebriefChat mistake={makeMistake()} />);

    await user.type(screen.getByLabelText("Tell the debrief"), "I guessed");
    await user.click(screen.getByRole("button", { name: "Send to the debrief" }));

    await waitFor(() => expect(screen.getByLabelText("Tell the debrief")).toHaveValue("I guessed"));
  });
});
