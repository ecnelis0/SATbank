import { expect, test } from "@playwright/test";

async function logOne(page: import("@playwright/test").Page, question: string) {
  await page.goto("/log");
  await page.getByRole("button", { name: "Reading & Writing" }).click();
  await page.getByLabel("The question").fill(question);
  await page.getByLabel("You put").fill("Lines 4-6");
  await page.getByLabel("The answer was").fill("Lines 20-22");
  await page.getByRole("button", { name: "Log it and ask the AI" }).click();
  await expect(page).toHaveURL(/\/bank\/[0-9a-f]{32}/);
}

test("the side panel answers a question in the student's own words", async ({ page }) => {
  const question = `Side panel evidence question ${Date.now() % 10000} [e2e]`;
  await logOne(page, question);

  await page.getByRole("button", { name: "Ask the bank" }).click();
  const panel = page.getByRole("complementary", { name: "Ask the bank" });
  await expect(panel).toBeVisible();

  await panel
    .getByLabel("Ask about your bank")
    .fill(
      "give me all the questions logged in the past 3 months that are very important " +
        "and from the reading category",
    );
  await panel.getByRole("button", { name: "Ask" }).click();

  // It reports what it searched for, and the hit is the real row.
  await expect(panel.getByText(/Searched:.*very important/)).toBeVisible({ timeout: 15_000 });
  await expect(panel.getByText(/Reading & Writing/).first()).toBeVisible();
  await expect(panel.getByText(question)).toBeVisible();

  // And the hit navigates to that question. The panel stays open across the
  // navigation, so the question is now on screen twice - scope to the page's article.
  await panel.getByText(question).click();
  await expect(page).toHaveURL(/\/bank\/[0-9a-f]{32}/);
  await expect(page.getByRole("article").getByText(question)).toBeVisible();
  await expect(panel).toBeVisible();
});

test("a filter that matches nothing says so rather than looking empty", async ({ page }) => {
  await logOne(page, `Nothing matches this ${Date.now() % 10000} [e2e]`);

  await page.getByRole("button", { name: "Ask the bank" }).click();
  const panel = page.getByRole("complementary", { name: "Ask the bank" });
  await panel.getByLabel("Ask about your bank").fill("fundamental math questions");
  await panel.getByRole("button", { name: "Ask" }).click();

  await expect(panel.getByText("Nothing matched. Try a looser question.")).toBeVisible({
    timeout: 15_000,
  });
  await expect(panel.getByText(/Searched:.*fundamental/)).toBeVisible();
});

test("the categories tab lists the bank and filters it", async ({ page }) => {
  const question = `Category browse ${Date.now() % 10000} [e2e]`;
  await logOne(page, question);

  await page.getByRole("button", { name: "Ask the bank" }).click();
  const panel = page.getByRole("complementary", { name: "Ask the bank" });
  await panel.getByRole("tab", { name: "Categories" }).click();

  await expect(panel.getByText("How urgent")).toBeVisible();
  await expect(panel.getByText("Section")).toBeVisible();
  await expect(panel.getByText("Why you missed it")).toBeVisible();

  await panel.getByRole("link", { name: /Reading & Writing/ }).click();
  await expect(page).toHaveURL(/\/bank\?section=reading_writing/);
  await expect(page.getByText(question)).toBeVisible({ timeout: 10_000 });
});

test("the panel closes again", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Ask the bank" }).click();
  await expect(page.getByRole("complementary", { name: "Ask the bank" })).toBeVisible();

  await page.getByRole("button", { name: "Close" }).click();
  await expect(page.getByRole("complementary", { name: "Ask the bank" })).toBeHidden();
});
