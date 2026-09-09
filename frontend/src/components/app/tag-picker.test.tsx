import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TagPicker } from "@/components/app/tag-picker";
import { api } from "@/lib/api";
import type { TagCount } from "@/lib/types";
import { renderWithQuery } from "@/test/render";

const KNOWN: TagCount[] = [
  { tag: "by mistake", count: 4, suggested: false },
  { tag: "ran out of time", count: 0, suggested: true },
];

describe("TagPicker", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("lets you invent a label and add it with Enter", async () => {
    vi.spyOn(api, "listTags").mockResolvedValue([]);
    const onChange = vi.fn();
    const user = userEvent.setup();

    renderWithQuery(<TagPicker selected={[]} onChange={onChange} />);
    await user.type(screen.getByLabelText("Add a label"), "forgot the +C{Enter}");

    expect(onChange).toHaveBeenCalledWith(["forgot the +C"]);
  });

  it("does not submit the form when Enter adds a label", async () => {
    vi.spyOn(api, "listTags").mockResolvedValue([]);
    const onSubmit = vi.fn((event: React.FormEvent) => event.preventDefault());
    const user = userEvent.setup();

    renderWithQuery(
      <form onSubmit={onSubmit}>
        <TagPicker selected={[]} onChange={vi.fn()} />
      </form>,
    );
    await user.type(screen.getByLabelText("Add a label"), "guessed{Enter}");

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("offers labels you have used before, with how often", async () => {
    vi.spyOn(api, "listTags").mockResolvedValue(KNOWN);

    renderWithQuery(<TagPicker selected={[]} onChange={vi.fn()} />);

    const used = await screen.findByRole("button", { name: /by mistake/ });
    expect(used).toHaveTextContent("4");
    expect(screen.getByRole("button", { name: /ran out of time/ })).toBeInTheDocument();
  });

  it("adds a suggested label in one click", async () => {
    vi.spyOn(api, "listTags").mockResolvedValue(KNOWN);
    const onChange = vi.fn();
    const user = userEvent.setup();

    renderWithQuery(<TagPicker selected={[]} onChange={onChange} />);
    await user.click(await screen.findByRole("button", { name: /ran out of time/ }));

    expect(onChange).toHaveBeenCalledWith(["ran out of time"]);
  });

  it("does not offer a label already chosen", async () => {
    vi.spyOn(api, "listTags").mockResolvedValue(KNOWN);

    renderWithQuery(<TagPicker selected={["by mistake"]} onChange={vi.fn()} />);

    await screen.findByRole("button", { name: /ran out of time/ });
    // Present once as a removable chip, never again as something to add.
    expect(
      screen.queryByRole("button", { name: /^by mistake/ }),
    ).not.toBeInTheDocument();
  });

  it("will not add the same label twice, whatever the case", async () => {
    vi.spyOn(api, "listTags").mockResolvedValue([]);
    const onChange = vi.fn();
    const user = userEvent.setup();

    renderWithQuery(<TagPicker selected={["by mistake"]} onChange={onChange} />);
    await user.type(screen.getByLabelText("Add a label"), "By Mistake{Enter}");

    expect(onChange).not.toHaveBeenCalled();
  });

  it("tidies stray spacing rather than storing it", async () => {
    vi.spyOn(api, "listTags").mockResolvedValue([]);
    const onChange = vi.fn();
    const user = userEvent.setup();

    renderWithQuery(<TagPicker selected={[]} onChange={onChange} />);
    await user.type(screen.getByLabelText("Add a label"), "  by   mistake  {Enter}");

    expect(onChange).toHaveBeenCalledWith(["by mistake"]);
  });

  it("removes a chosen label", async () => {
    vi.spyOn(api, "listTags").mockResolvedValue([]);
    const onChange = vi.fn();
    const user = userEvent.setup();

    renderWithQuery(<TagPicker selected={["guessed"]} onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: "Remove label guessed" }));

    await waitFor(() => expect(onChange).toHaveBeenCalledWith([]));
  });
});
