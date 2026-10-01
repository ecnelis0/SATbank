import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { VideoForm } from "@/components/app/video-form";
import { api } from "@/lib/api";
import { renderWithQuery } from "@/test/render";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

const video = {
  id: "v1",
  created_at: "2026-09-30T00:00:00Z",
  youtube_id: "dQw4w9WgXcQ",
  url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  title: "Semicolons",
  author: "A channel",
  subject: "grammar",
  directions: null,
  status: "pending" as const,
  error: null,
  summary: null,
  duration_seconds: null,
  summarised_at: null,
  concept_count: 0,
  has_transcript: false,
};

describe("VideoForm", () => {
  it("will not submit without a link", () => {
    renderWithQuery(<VideoForm />);
    expect(screen.getByRole("button", { name: "Add the video" })).toBeDisabled();
  });

  it("sends the link, the tab and the directions", async () => {
    const user = userEvent.setup();
    const add = vi.spyOn(api, "addVideo").mockResolvedValue(video);
    renderWithQuery(<VideoForm />);

    await user.type(screen.getByLabelText("YouTube link"), "https://youtu.be/dQw4w9WgXcQ");
    await user.click(screen.getByRole("button", { name: "grammar" }));
    await user.type(
      screen.getByLabelText("Anything the AI should do with it?"),
      "Only the comma rules.",
    );
    await user.click(screen.getByRole("button", { name: "Add the video" }));

    await waitFor(() =>
      expect(add).toHaveBeenCalledWith({
        url: "https://youtu.be/dQw4w9WgXcQ",
        subject: "grammar",
        directions: "Only the comma rules.",
        transcript: null,
      }),
    );
  });

  it("opens the video it just added", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "addVideo").mockResolvedValue(video);
    renderWithQuery(<VideoForm />);

    await user.type(screen.getByLabelText("YouTube link"), "https://youtu.be/dQw4w9WgXcQ");
    await user.click(screen.getByRole("button", { name: "Add the video" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/videos/v1"));
  });

  it("offers the transcript box for a video with no captions", async () => {
    const user = userEvent.setup();
    const add = vi.spyOn(api, "addVideo").mockResolvedValue(video);
    renderWithQuery(<VideoForm />);

    // Hidden until asked for: most videos have captions and the box is long.
    expect(screen.queryByLabelText("Transcript")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /no captions/ }));

    await user.type(screen.getByLabelText("YouTube link"), "https://youtu.be/dQw4w9WgXcQ");
    await user.type(screen.getByLabelText("Transcript"), "A semicolon joins two clauses.");
    await user.click(screen.getByRole("button", { name: "Add the video" }));

    await waitFor(() =>
      expect(add).toHaveBeenCalledWith(
        expect.objectContaining({ transcript: "A semicolon joins two clauses." }),
      ),
    );
  });

  it("says what went wrong rather than failing silently", async () => {
    const user = userEvent.setup();
    const { toast } = await import("sonner");
    vi.spyOn(api, "addVideo").mockRejectedValue(
      new Error("That does not look like a YouTube link."),
    );
    renderWithQuery(<VideoForm />);

    await user.type(screen.getByLabelText("YouTube link"), "https://vimeo.com/123");
    await user.click(screen.getByRole("button", { name: "Add the video" }));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("That does not look like a YouTube link."),
    );
  });
});
