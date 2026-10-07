import { waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ScanQuestion } from "@/components/app/scan-question";
import { api } from "@/lib/api";
import { renderWithQuery } from "@/test/render";

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  }),
}));

const png = (name: string) =>
  new File([new Uint8Array([137, 80, 78, 71])], name, { type: "image/png" });

/** react-dropzone hides its input from the accessibility tree, so it is reached
 *  by label rather than by role. */
function dropzoneInput(): HTMLInputElement {
  const input = document.querySelector<HTMLInputElement>(
    'input[type="file"][aria-label="Scan a screenshot"]',
  );
  if (!input) throw new Error("no scanner file input");
  return input;
}

describe("ScanQuestion without AI", () => {
  it("keeps the picture when the reading fails", async () => {
    // Dropping a picture must do something useful with no AI at all: running out
    // of usage should cost the typing it would have saved, and nothing else.
    const user = userEvent.setup();
    const onScanned = vi.fn();
    const onKeepPicture = vi.fn();
    vi.spyOn(api, "scanQuestion").mockRejectedValue(new Error("out of usage"));

    renderWithQuery(<ScanQuestion onScanned={onScanned} onKeepPicture={onKeepPicture} />);
    await user.upload(dropzoneInput(), png("q.png"));

    await waitFor(() => expect(onKeepPicture).toHaveBeenCalled());
    expect(onKeepPicture.mock.calls[0][0].name).toBe("q.png");
    expect(onScanned).not.toHaveBeenCalled();
  });

  it("keeps the picture when the reader saw nothing in it", async () => {
    const user = userEvent.setup();
    const onKeepPicture = vi.fn();
    vi.spyOn(api, "scanQuestion").mockResolvedValue({
      question_text: "",
      answer_source: "unknown",
      note: "The offline reader cannot see pictures.",
    });

    renderWithQuery(<ScanQuestion onScanned={vi.fn()} onKeepPicture={onKeepPicture} />);
    await user.upload(dropzoneInput(), png("q.png"));

    await waitFor(() => expect(onKeepPicture).toHaveBeenCalled());
  });

  it("still fills the form when the reading works", async () => {
    const user = userEvent.setup();
    const onScanned = vi.fn();
    const onKeepPicture = vi.fn();
    vi.spyOn(api, "scanQuestion").mockResolvedValue({
      question_text: "If 3x + 7 = 22, what is x?",
      answer_source: "stated",
      correct_answer: "5",
    });

    renderWithQuery(<ScanQuestion onScanned={onScanned} onKeepPicture={onKeepPicture} />);
    await user.upload(dropzoneInput(), png("q.png"));

    await waitFor(() => expect(onScanned).toHaveBeenCalled());
    // The picture goes on through the success path, so it must not be added twice.
    expect(onKeepPicture).not.toHaveBeenCalled();
  });
});
