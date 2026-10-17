import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AiSwitch } from "@/components/app/ai-switch";
import { api } from "@/lib/api";
import type { AiChoice, ProviderId } from "@/lib/types";
import { renderWithQuery } from "@/test/render";

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), warning: vi.fn() }),
}));

function choice(provider: ProviderId, ready = true): AiChoice {
  const label = { agent: "Claude", openai: "OpenAI", claude: "Claude API", stub: "AI off" };
  return {
    provider,
    label: label[provider],
    ready,
    source: "switch",
    options: (["agent", "openai", "claude", "stub"] as const).map((id) => ({
      id,
      label: label[id],
      description: `${label[id]} description`,
      ready: id === provider ? ready : true,
    })),
  };
}

afterEach(() => vi.restoreAllMocks());

describe("AiSwitch", () => {
  it("shows Claude and OpenAI, with the one in use checked", async () => {
    vi.spyOn(api, "ai").mockResolvedValue(choice("openai"));
    renderWithQuery(<AiSwitch />);

    const openai = await screen.findByRole("radio", { name: "OpenAI" });
    expect(openai).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: "Claude" })).toHaveAttribute(
      "aria-checked",
      "false",
    );
    // The two rarely-used ones live in ./ai.sh, not in the nav.
    expect(screen.queryByRole("radio", { name: "AI off" })).not.toBeInTheDocument();
  });

  it("switches on click and shows the new choice", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "ai").mockResolvedValue(choice("openai"));
    const flip = vi.spyOn(api, "switchAi").mockResolvedValue(choice("agent"));
    renderWithQuery(<AiSwitch />);

    await user.click(await screen.findByRole("radio", { name: "Claude" }));

    expect(flip).toHaveBeenCalledWith("agent");
    await waitFor(() =>
      expect(screen.getByRole("radio", { name: "Claude" })).toHaveAttribute(
        "aria-checked",
        "true",
      ),
    );
  });

  it("does not re-send the choice already in use", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "ai").mockResolvedValue(choice("agent"));
    const flip = vi.spyOn(api, "switchAi");
    renderWithQuery(<AiSwitch />);

    await user.click(await screen.findByRole("radio", { name: "Claude" }));
    expect(flip).not.toHaveBeenCalled();
  });

  it("warns when the chosen one has no key", async () => {
    const { toast } = await import("sonner");
    const user = userEvent.setup();
    vi.spyOn(api, "ai").mockResolvedValue(choice("agent"));
    vi.spyOn(api, "switchAi").mockResolvedValue(choice("openai", false));
    renderWithQuery(<AiSwitch />);

    await user.click(await screen.findByRole("radio", { name: "OpenAI" }));
    await waitFor(() => expect(toast.warning).toHaveBeenCalled());
  });
});
