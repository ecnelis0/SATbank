import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AnalysisPanel } from "@/components/app/analysis";
import { api } from "@/lib/api";
import { makeMistake } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

const unanalysed = () =>
  makeMistake({
    analysis_status: "not_requested",
    analyzed_by: null,
    analyzed_at: null,
    error_type: null,
    topic: null,
    difficulty: null,
    why_wrong: null,
    correct_reasoning: null,
    takeaway: null,
    trap: null,
    tags: null,
  });

describe("AnalysisPanel", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("offers the debrief on a question logged by hand, rather than pretending to work", () => {
    renderWithQuery(<AnalysisPanel mistake={unanalysed()} editable />);

    expect(screen.getByText(/No debrief yet/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Ask the AI to debrief this" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Write it myself" })).toBeInTheDocument();
  });

  it("asks the AI when the student asks for it", async () => {
    const mistake = unanalysed();
    const analyze = vi.spyOn(api, "analyze").mockResolvedValue(makeMistake());
    const user = userEvent.setup();

    renderWithQuery(<AnalysisPanel mistake={mistake} editable />);
    await user.click(screen.getByRole("button", { name: "Ask the AI to debrief this" }));

    await waitFor(() => expect(analyze).toHaveBeenCalledWith(mistake.id, false));
  });

  it("lets the student write the whole analysis themselves", async () => {
    const mistake = unanalysed();
    const update = vi.spyOn(api, "updateMistake").mockResolvedValue(makeMistake());
    const user = userEvent.setup();

    renderWithQuery(<AnalysisPanel mistake={mistake} editable />);
    await user.click(screen.getByRole("button", { name: "Write it myself" }));

    await user.selectOptions(
      screen.getByLabelText("Why you got it wrong"),
      "time_pressure_guess",
    );
    await user.clear(screen.getByLabelText("Topic"));
    await user.type(screen.getByLabelText("Topic"), "linear equations");
    await user.type(screen.getByLabelText("Remember"), "Read the constant twice.");
    await user.type(screen.getByLabelText("Tags"), "algebra, careless");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(update).toHaveBeenCalledWith(
        mistake.id,
        expect.objectContaining({
          error_type: "time_pressure_guess",
          topic: "linear equations",
          takeaway: "Read the constant twice.",
          tags: ["algebra", "careless"],
        }),
      ),
    );
  });

  it("edits an existing analysis starting from what is already there", async () => {
    const mistake = makeMistake();
    const update = vi.spyOn(api, "updateMistake").mockResolvedValue(mistake);
    const user = userEvent.setup();

    renderWithQuery(<AnalysisPanel mistake={mistake} editable />);
    await user.click(screen.getByRole("button", { name: "Edit" }));

    // The editor is seeded with the AI's text, not blank.
    expect(screen.getByLabelText("Remember")).toHaveValue(mistake.takeaway);

    await user.clear(screen.getByLabelText("Remember"));
    await user.type(screen.getByLabelText("Remember"), "My own words.");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(update).toHaveBeenCalledWith(
        mistake.id,
        expect.objectContaining({ takeaway: "My own words." }),
      ),
    );
  });

  it("cancelling an edit changes nothing", async () => {
    const update = vi.spyOn(api, "updateMistake");
    const user = userEvent.setup();

    renderWithQuery(<AnalysisPanel mistake={makeMistake()} editable />);
    await user.click(screen.getByRole("button", { name: "Edit" }));
    await user.type(screen.getByLabelText("Remember"), " and more");
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(update).not.toHaveBeenCalled();
    expect(screen.getByText("Why you got it wrong")).toBeInTheDocument();
  });

  it("warns before an AI re-run overwrites something the student wrote", async () => {
    const mistake = makeMistake({ analysis_edited_at: new Date().toISOString() });
    const analyze = vi.spyOn(api, "analyze").mockResolvedValue(mistake);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const user = userEvent.setup();

    renderWithQuery(<AnalysisPanel mistake={mistake} editable />);
    await user.click(screen.getByRole("button", { name: "Re-run the AI" }));

    expect(confirm).toHaveBeenCalled();
    expect(analyze).not.toHaveBeenCalled();

    confirm.mockReturnValue(true);
    await user.click(screen.getByRole("button", { name: "Re-run the AI" }));
    // Confirmed, so it goes through with force - the backend refuses otherwise.
    await waitFor(() => expect(analyze).toHaveBeenCalledWith(mistake.id, true));
  });

  it("does not interrupt a re-run when the analysis is untouched", async () => {
    const mistake = makeMistake();
    const analyze = vi.spyOn(api, "analyze").mockResolvedValue(mistake);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();

    renderWithQuery(<AnalysisPanel mistake={mistake} editable />);
    await user.click(screen.getByRole("button", { name: "Re-run the AI" }));

    expect(confirm).not.toHaveBeenCalled();
    await waitFor(() => expect(analyze).toHaveBeenCalledWith(mistake.id, false));
  });

  it("says who wrote the analysis", () => {
    const { rerender } = renderWithQuery(<AnalysisPanel mistake={makeMistake()} />);
    expect(screen.getByText("Analysis by stub.")).toBeInTheDocument();

    rerender(
      <AnalysisPanel
        mistake={makeMistake({
          analyzed_by: "you",
          analysis_edited_at: new Date().toISOString(),
        })}
      />,
    );
    expect(screen.getByText("Written by you.")).toBeInTheDocument();
  });

  it("offers no edit controls where the panel is read-only", () => {
    renderWithQuery(<AnalysisPanel mistake={makeMistake()} />);

    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Re-run the AI" })).not.toBeInTheDocument();
  });
});
