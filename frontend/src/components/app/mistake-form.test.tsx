import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { formatChoices, MistakeForm } from "@/components/app/mistake-form";
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

/** The dropzone's file input is hidden from the accessibility tree by react-dropzone,
 *  so it is reached by its aria-label rather than by role.
 *
 *  By label and not by position: the form has two file inputs — the scanner at
 *  the top and the pictures further down — and `querySelector` returning
 *  whichever comes first silently moved every picture test onto the scanner the
 *  moment the scanner was added. */
function dropzoneInput(label = "Add a picture"): HTMLInputElement {
  const input = document.querySelector<HTMLInputElement>(
    `input[type="file"][aria-label="${label}"]`,
  );
  if (!input) throw new Error(`no file input labelled "${label}"`);
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

describe("MistakeForm scanning a question", () => {
  const scanned = {
    question_text: "Which finding, if true, would most directly support the hypothesis?",
    choices: ["The LINE transposon is active in an octopus brain structure.", "The human genome contains multiple transposons."],
    correct_answer: "A",
    answer_source: "worked" as const,
    section: "reading_writing" as const,
    source: "SAT Question Bank, ID 22e4d633",
    note: null,
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    push.mockClear();
  });

  it("fills the form from what was read, and leaves your answer to you", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "scanQuestion").mockResolvedValue(scanned);
    renderWithQuery(<MistakeForm />);

    await user.upload(dropzoneInput("Scan a screenshot"), png("q.png"));

    expect(await screen.findByDisplayValue(scanned.question_text)).toBeInTheDocument();
    expect(screen.getByLabelText("The answer was")).toHaveValue("A");
    expect(screen.getByLabelText("Where it came from")).toHaveValue(scanned.source);
    // Labelled, with a blank line between, so four options read as four things.
    // parseChoices strips the labels again on the way back to the API.
    expect(screen.getByLabelText("Answer choices")).toHaveValue(
      formatChoices(scanned.choices),
    );
    // The one box a picture cannot fill, and the reason the bank exists.
    expect(screen.getByLabelText("You put")).toHaveValue("");
    // The section it read wins over the form's default of Math.
    expect(screen.getByRole("button", { name: "Reading & Writing" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("warns when the answer was worked out rather than printed on the page", async () => {
    const user = userEvent.setup();
    const { toast } = await import("sonner");
    vi.spyOn(api, "scanQuestion").mockResolvedValue(scanned);
    renderWithQuery(<MistakeForm />);

    await user.upload(dropzoneInput("Scan a screenshot"), png("q.png"));

    await waitFor(() =>
      expect(toast.success).toHaveBeenCalledWith(expect.stringContaining("worked out")),
    );
  });

  it("does not warn when the page stated the answer", async () => {
    const user = userEvent.setup();
    const { toast } = await import("sonner");
    vi.spyOn(api, "scanQuestion").mockResolvedValue({ ...scanned, answer_source: "stated" });
    renderWithQuery(<MistakeForm />);

    await user.upload(dropzoneInput("Scan a screenshot"), png("q.png"));

    await waitFor(() => expect(toast.success).toHaveBeenCalled());
    expect(toast.success).not.toHaveBeenCalledWith(expect.stringContaining("worked out"));
  });

  it("keeps the picture it read, so it is attached to the question", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "scanQuestion").mockResolvedValue(scanned);
    renderWithQuery(<MistakeForm />);

    await user.upload(dropzoneInput("Scan a screenshot"), png("q.png"));

    expect(await screen.findByRole("img", { name: "Picture 1 to upload" })).toBeInTheDocument();
  });

  it("logs nothing on its own — scanning only fills the form", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "scanQuestion").mockResolvedValue(scanned);
    const log = vi.spyOn(api, "logMistake").mockResolvedValue(makeMistake());
    renderWithQuery(<MistakeForm />);

    await user.upload(dropzoneInput("Scan a screenshot"), png("q.png"));
    await screen.findByDisplayValue(scanned.question_text);

    expect(log).not.toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();
  });

  it("says so rather than filling the form with blanks when nothing was read", async () => {
    const user = userEvent.setup();
    const { toast } = await import("sonner");
    vi.spyOn(api, "scanQuestion").mockResolvedValue({
      question_text: "",
      answer_source: "unknown",
      note: "The offline reader cannot see pictures.",
    });
    renderWithQuery(<MistakeForm />);

    await user.upload(dropzoneInput("Scan a screenshot"), png("q.png"));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("The offline reader cannot see pictures."),
    );
    expect(screen.getByLabelText("The question")).toHaveValue("");
  });
});

describe("MistakeForm the draft", () => {
  it("still has what you typed after you leave the page and come back", async () => {
    const user = userEvent.setup();
    const first = renderWithQuery(<MistakeForm />);

    await user.type(screen.getByLabelText("The question"), "If 3x + 7 = 22, what is x?");
    await user.type(screen.getByLabelText("You put"), "15");
    await waitFor(() =>
      expect(screen.getByLabelText("You put")).toHaveValue("15"),
    );

    // Leaving the tab is an unmount, which is the case this exists for.
    first.unmount();
    renderWithQuery(<MistakeForm />);

    expect(await screen.findByDisplayValue("If 3x + 7 = 22, what is x?")).toBeInTheDocument();
    expect(screen.getByLabelText("You put")).toHaveValue("15");
  });

  it("comes back empty when nothing was typed", async () => {
    const first = renderWithQuery(<MistakeForm />);
    first.unmount();
    renderWithQuery(<MistakeForm />);

    expect(screen.getByLabelText("The question")).toHaveValue("");
  });

  it("throws it away on Clear everything, and keeps it thrown away", async () => {
    const user = userEvent.setup();
    const first = renderWithQuery(<MistakeForm />);
    await user.type(screen.getByLabelText("The question"), "Something I typed");

    await user.click(screen.getByRole("button", { name: "Clear everything" }));
    expect(screen.getByLabelText("The question")).toHaveValue("");

    // The clear has to outlive the page too: the first version of the store
    // handed the cleared draft straight back on the next visit.
    first.unmount();
    renderWithQuery(<MistakeForm />);
    expect(screen.getByLabelText("The question")).toHaveValue("");
  });

  it("is gone once the question is actually logged", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "logMistake").mockResolvedValue(makeMistake());
    const first = renderWithQuery(<MistakeForm />);

    await fillTheQuestion(user);
    await user.click(screen.getByRole("button", { name: "Log it and ask the AI" }));
    await waitFor(() => expect(push).toHaveBeenCalled());

    first.unmount();
    renderWithQuery(<MistakeForm />);
    expect(screen.getByLabelText("The question")).toHaveValue("");
  });
});
