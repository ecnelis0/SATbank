import { expect, test, type Page } from "@playwright/test";

/** The e2e stack runs the offline analyzer, so these check the plumbing - kept,
 *  shown, re-rendered - not the quality of what a model would write. */

// Whatever happens in a test - including the switch test failing halfway - the
// suite must go back to the offline reader rather than call a real model.
const offline = async ({ request }: { request: import("@playwright/test").APIRequestContext }) => {
  await request.put("http://127.0.0.1:8001/ai", { data: { provider: "stub" } });
};
test.beforeEach(offline);
test.afterEach(offline);

async function logAndDebrief(page: Page) {
  await page.goto("/log");
  await page
    .getByLabel("The question")
    .fill(`If 4x - 2 = ${Date.now() % 1000}, what is x? [e2e debrief chat]`);
  await page.getByLabel("You put").fill("9");
  await page.getByLabel("The answer was").fill("11");
  await page.getByRole("button", { name: "Just log it" }).click();
  await expect(page).toHaveURL(/\/bank\/[0-9a-f]{32}/);
  await page.getByRole("button", { name: "Ask the AI to debrief this" }).click();
  await expect(page.getByText("WHY YOU GOT IT WRONG")).toBeVisible({ timeout: 15_000 });
}

test("what is said to the debrief is answered, and still there after a reload", async ({
  page,
}) => {
  await logAndDebrief(page);

  const box = page.getByLabel("Tell the debrief");
  await box.click();
  await box.fill("I misread it - I solved for 4x.");
  await page.getByRole("button", { name: "Send to the debrief" }).click();

  const conversation = page.getByRole("list", { name: "Conversation with the debrief" });
  await expect(conversation.getByText("I misread it - I solved for 4x.", { exact: true })).toBeVisible();
  // The offline reader says it heard and cannot act - it never pretends to.
  await expect(conversation.getByText(/offline reader cannot rewrite/)).toBeVisible({
    timeout: 15_000,
  });

  await page.reload();
  await expect(
    page
      .getByRole("list", { name: "Conversation with the debrief" })
      .getByText("I misread it - I solved for 4x.", { exact: true }),
  ).toBeVisible();
});

test("a command in the ask chat goes into the debrief's kept conversation", async ({
  page,
}) => {
  await logAndDebrief(page);

  const ask = page.getByLabel("Ask about this question");
  await ask.click();
  await ask.fill("Consider this in the debrief: I ran out of time.");
  await page.getByRole("button", { name: "Ask", exact: true }).click();

  await expect(page.getByText("Debrief updated")).toBeVisible({ timeout: 15_000 });
  await expect(
    page
      .getByRole("list", { name: "Conversation with the debrief" })
      .getByText("Consider this in the debrief: I ran out of time.", { exact: true }),
  ).toBeVisible();
});

test("an analysis of the whole bank is written, kept and can be reopened", async ({
  page,
}) => {
  await logAndDebrief(page);

  await page.goto("/insights");
  await page.getByLabel("What to look at").fill("What do I keep doing? [e2e]");
  await page.getByRole("button", { name: "Analyse my bank" }).click();

  const analysis = page.getByRole("article", { name: "Analysis" });
  await expect(analysis.getByText("What do I keep doing? [e2e]")).toBeVisible({
    timeout: 15_000,
  });
  await expect(analysis.getByText("Right on review")).toBeVisible();

  await page.reload();
  await expect(
    page.getByRole("button", { name: /What do I keep doing\? \[e2e\]/ }),
  ).toBeVisible();
});

test("the nav switch changes which AI answers", async ({ page }) => {
  await page.goto("/");
  const group = page.getByRole("radiogroup", { name: "Which AI to use" });
  const claude = group.getByRole("radio", { name: "Claude" });
  const openai = group.getByRole("radio", { name: "OpenAI" });
  await expect(claude).toBeVisible();

  // Real pointer, at the button's own centre.
  const box = (await claude.boundingBox())!;
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await expect(claude).toHaveAttribute("aria-checked", "true");
  const health = await (await page.request.get("http://127.0.0.1:8001/health")).json();
  expect(health.analyzer).toBe("agent");

  // Put it back to the offline reader, so the rest of the suite never calls a model.
  await page.request.put("http://127.0.0.1:8001/ai", { data: { provider: "stub" } });
  await page.reload();
  await expect(openai).toHaveAttribute("aria-checked", "false");
  await expect(claude).toHaveAttribute("aria-checked", "false");
});
