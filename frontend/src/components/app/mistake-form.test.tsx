import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MistakeForm } from "@/components/app/mistake-form";
import { api } from "@/lib/api";
import { makeMistake } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

const png = (name: string) =>
  new File([new Uint8Array([137, 80, 78, 71])], name, { type: "image/png" });

async function fillTheQuestion(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("The question"), "If 3x + 7 = 22, what is x?");
  await user.type(screen.getByLabelText("You put"), "7");
  await user.type(screen.getByLabelText("The answer was"), "5");
}

/** The dropzone's file input is hidden from the accessibility tree by react-dropzone. */
function dropzoneInput(): HTMLInputElement {
  const input = document.querySelector<HTMLInputElement>('input[type="file"]');
  if (!input) throw new Error("no file input rendered");
  return input;
}

describe("MistakeForm pictures", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    push.mockClear();
  });

  it("previews a picture chosen before the question is saved", async () => {
    const user = userEvent.setup();
    renderWithQuery(<MistakeForm />);

    await user.upload(dropzoneInput(), png("shot.png"));

    expect(
      await screen.findByRole("img", { name: "Picture 1 to upload" }),
    ).toBeInTheDocument();
  });

  it("uploads the pictures after the question exists, in the order they were added", async () => {
    const mistake = makeMistake();
    vi.spyOn(api, "logMistake").mockResolvedValue(mistake);
    const order: string[] = [];
    const upload = vi.spyOn(api, "uploadImage").mockImplementation(async (_id, file) => {
      order.push(file.name);
      return mistake;
    });
    const user = userEvent.setup();

    renderWithQuery(<MistakeForm />);
    await fillTheQuestion(user);
    await user.upload(dropzoneInput(), [png("one.png"), png("two.png")]);
    await user.click(screen.getByRole("button", { name: "Log it and ask the AI" }));

    await waitFor(() => expect(upload).toHaveBeenCalledTimes(2));
    expect(order).toEqual(["one.png", "two.png"]);
    // Uploaded against the id the question came back with, not a guess.
    expect(upload).toHaveBeenCalledWith(mistake.id, expect.any(File));
  });

  it("does not upload anything before the question is saved", async () => {
    const upload = vi.spyOn(api, "uploadImage");
    const user = userEvent.setup();

    renderWithQuery(<MistakeForm />);
    await user.upload(dropzoneInput(), png("shot.png"));
    await screen.findByRole("img", { name: "Picture 1 to upload" });

    expect(upload).not.toHaveBeenCalled();
  });

  it("a chosen picture can be dropped again before saving", async () => {
    const user = userEvent.setup();
    renderWithQuery(<MistakeForm />);

    await user.upload(dropzoneInput(), png("shot.png"));
    await user.click(await screen.findByRole("button", { name: "Remove picture 1" }));

    expect(
      screen.queryByRole("img", { name: "Picture 1 to upload" }),
    ).not.toBeInTheDocument();
  });

  it("keeps the question when a picture fails to upload", async () => {
    const mistake = makeMistake();
    vi.spyOn(api, "logMistake").mockResolvedValue(mistake);
    vi.spyOn(api, "uploadImage").mockRejectedValue(new Error("too big"));
    const { toast } = await import("sonner");
    const user = userEvent.setup();

    renderWithQuery(<MistakeForm />);
    await fillTheQuestion(user);
    await user.upload(dropzoneInput(), png("huge.png"));
    await user.click(screen.getByRole("button", { name: "Log it and ask the AI" }));

    // The question is saved and the student is taken to it; only the picture is lost.
    await waitFor(() => expect(push).toHaveBeenCalledWith(`/bank/${mistake.id}`));
    expect(toast.error).toHaveBeenCalledWith(expect.stringContaining("1 picture"));
  });

  it("logs a question with no pictures exactly as before", async () => {
    const mistake = makeMistake();
    const log = vi.spyOn(api, "logMistake").mockResolvedValue(mistake);
    const upload = vi.spyOn(api, "uploadImage");
    const user = userEvent.setup();

    renderWithQuery(<MistakeForm />);
    await fillTheQuestion(user);
    await user.click(screen.getByRole("button", { name: "Just log it" }));

    await waitFor(() => expect(log).toHaveBeenCalledWith(expect.anything(), false));
    expect(upload).not.toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith(`/bank/${mistake.id}`);
  });

  it("will not save a question that is missing its answers", async () => {
    const log = vi.spyOn(api, "logMistake");
    const user = userEvent.setup();

    renderWithQuery(<MistakeForm />);
    await user.type(screen.getByLabelText("The question"), "Only the question");
    await user.click(screen.getByRole("button", { name: "Log it and ask the AI" }));

    expect(await screen.findByText("What did you put?")).toBeInTheDocument();
    expect(log).not.toHaveBeenCalled();
  });
});
