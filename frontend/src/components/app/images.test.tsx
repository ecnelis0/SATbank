import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MistakeImages, imageSrc } from "@/components/app/images";
import { API_URL, api } from "@/lib/api";
import type { Mistake, MistakeImage } from "@/lib/types";
import { makeMistake } from "@/test/fixtures";
import { renderWithQuery } from "@/test/render";

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

function image(overrides: Partial<MistakeImage> = {}): MistakeImage {
  return {
    id: "i1",
    url: "/uploads/abc123.png",
    content_type: "image/png",
    byte_size: 1024,
    width: 800,
    height: 600,
    caption: null,
    position: 0,
    ...overrides,
  };
}

function withImages(...images: MistakeImage[]): Mistake {
  return makeMistake({ images });
}

const file = (name = "shot.png") =>
  new File([new Uint8Array([137, 80, 78, 71])], name, { type: "image/png" });

describe("MistakeImages", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("points at the API's origin, not the web app's", () => {
    expect(imageSrc(image())).toBe(`${API_URL}/uploads/abc123.png`);
  });

  it("leaves an absolute URL alone", () => {
    expect(imageSrc(image({ url: "https://cdn.example.com/x.png" }))).toBe(
      "https://cdn.example.com/x.png",
    );
  });

  it("shows each attached picture", () => {
    renderWithQuery(
      <MistakeImages mistake={withImages(image(), image({ id: "i2", url: "/uploads/b.png" }))} />,
    );

    expect(screen.getAllByRole("img")).toHaveLength(2);
  });

  it("says so when there are none", () => {
    renderWithQuery(<MistakeImages mistake={makeMistake()} />);

    expect(screen.getByText("No pictures.")).toBeInTheDocument();
  });

  it("uploads a chosen file", async () => {
    const upload = vi.spyOn(api, "uploadImage").mockResolvedValue(withImages(image()));
    const mistake = makeMistake();
    const user = userEvent.setup();

    renderWithQuery(<MistakeImages mistake={mistake} editable />);
    await user.upload(screen.getByLabelText("Add a picture"), file());

    await waitFor(() =>
      expect(upload).toHaveBeenCalledWith(mistake.id, expect.any(File)),
    );
  });

  it("uploads several files one after another, so their order is not a race", async () => {
    const order: string[] = [];
    vi.spyOn(api, "uploadImage").mockImplementation(async (_id, uploaded) => {
      order.push(uploaded.name);
      return withImages(image());
    });
    const user = userEvent.setup();

    renderWithQuery(<MistakeImages mistake={makeMistake()} editable />);
    await user.upload(screen.getByLabelText("Add a picture"), [
      file("one.png"),
      file("two.png"),
      file("three.png"),
    ]);

    await waitFor(() => expect(order).toEqual(["one.png", "two.png", "three.png"]));
  });

  it("reports a rejected upload rather than failing silently", async () => {
    vi.spyOn(api, "uploadImage").mockRejectedValue(
      new Error("That file is not an image we can read."),
    );
    const { toast } = await import("sonner");
    const user = userEvent.setup();

    renderWithQuery(<MistakeImages mistake={makeMistake()} editable />);
    await user.upload(screen.getByLabelText("Add a picture"), file("evil.png"));

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("That file is not an image we can read."),
    );
  });

  it("deletes a picture", async () => {
    const remove = vi.spyOn(api, "deleteImage").mockResolvedValue(makeMistake());
    const mistake = withImages(image());
    const user = userEvent.setup();

    renderWithQuery(<MistakeImages mistake={mistake} editable />);
    await user.click(screen.getByRole("button", { name: "Delete picture 1" }));

    await waitFor(() => expect(remove).toHaveBeenCalledWith(mistake.id, "i1"));
  });

  it("offers no upload or delete controls when read-only", () => {
    renderWithQuery(<MistakeImages mistake={withImages(image())} />);

    expect(screen.queryByLabelText("Add a picture")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Delete picture 1" }),
    ).not.toBeInTheDocument();
  });
});

describe("MistakeImages zoom", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("opens the zoom view on the picture that was clicked", async () => {
    const user = userEvent.setup();
    renderWithQuery(
      <MistakeImages
        mistake={withImages(
          image({ id: "i1", url: "/uploads/first.png" }),
          image({ id: "i2", url: "/uploads/second.png" }),
        )}
      />,
    );

    // Index 0 is a real index; a falsy check would swallow the first picture.
    await user.click(screen.getByRole("button", { name: "Open picture 1 full size" }));

    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByRole("img", { name: "Picture 1 of the question" }),
    ).toHaveAttribute("src", `${API_URL}/uploads/first.png`);
  });

  it("opens on the second picture when the second is clicked", async () => {
    const user = userEvent.setup();
    const { container } = renderWithQuery(
      <MistakeImages
        mistake={withImages(
          image({ id: "i1", url: "/uploads/first.png" }),
          image({ id: "i2", url: "/uploads/second.png" }),
        )}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Open picture 2 full size" }));
    await screen.findByRole("dialog");

    // The lightbox preloads its neighbours, so "present in the dialog" is not the
    // same as "the slide you are looking at".
    const current = container.ownerDocument.querySelector(".yarl__slide_current img");
    expect(current).toHaveAttribute("src", `${API_URL}/uploads/second.png`);
  });

  it("is closed until a picture is clicked", () => {
    renderWithQuery(<MistakeImages mistake={withImages(image())} />);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes again", async () => {
    const user = userEvent.setup();
    renderWithQuery(<MistakeImages mistake={withImages(image())} />);

    await user.click(screen.getByRole("button", { name: "Open picture 1 full size" }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /close/i }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});
