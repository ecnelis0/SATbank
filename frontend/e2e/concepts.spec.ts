import { expect, test, type Page } from "@playwright/test";

async function logQuestion(page: Page, question: string) {
  await page.goto("/log");
  await page.getByLabel("The question").fill(question);
  await page.getByLabel("You put").fill("12π");
  await page.getByLabel("The answer was").fill("36π");
  await page.getByRole("button", { name: "Just log it" }).click();
  await expect(page).toHaveURL(/\/bank\/[0-9a-f]{32}/);
  return page.url();
}

test("a concept is written once, then questions are tagged onto it afterwards", async ({
  page,
}) => {
  const stamp = Date.now() % 100000;
  const title = `Circumference gives the radius first ${stamp}`;
  const question = `Concept tagging question ${stamp} [e2e]`;

  // 1. Write the concept from its own tab.
  await page.goto("/concepts");
  await page.getByRole("button", { name: "Write a concept" }).click();
  await page.getByLabel("The concept").fill(title);
  await page
    .getByLabel("In your own words")
    .fill("C = 2πr, so r = C / 2π. Do that step before anything else.");
  await page.getByLabel("Section").selectOption("math");
  await page.getByRole("button", { name: "Add concept" }).click();
  await expect(page.getByText(title)).toBeVisible();

  // 2. Log a question, which starts untagged.
  const questionUrl = await logQuestion(page, question);
  await expect(page.getByText("Not filed under any concept yet.")).toBeVisible();

  // 3. Tag it after the fact.
  await page.getByRole("button", { name: "Tag with a concept" }).click();
  await page.getByRole("button", { name: title }).click();
  await expect(page.getByRole("link", { name: title })).toBeVisible();

  // 4. The concept now collects that question, from its own page.
  await page.getByRole("link", { name: title }).click();
  await expect(page).toHaveURL(/\/concepts\/[0-9a-f]{32}/);
  await expect(page.getByText("C = 2πr")).toBeVisible();
  await expect(page.getByText(question)).toBeVisible();

  // 5. And the tag survives a reload of the question.
  await page.goto(questionUrl);
  await expect(page.getByRole("link", { name: title })).toBeVisible();
});

test("a concept filters the bank, and untagging removes only the tag", async ({ page }) => {
  const stamp = Date.now() % 100000;
  const title = `Filterable concept ${stamp}`;
  const tagged = `Alpha question ${stamp} [e2e]`;
  const untagged = `Omega question ${stamp} [e2e]`;

  await page.goto("/concepts");
  await page.getByRole("button", { name: "Write a concept" }).click();
  await page.getByLabel("The concept").fill(title);
  await page.getByRole("button", { name: "Add concept" }).click();
  await expect(page.getByText(title)).toBeVisible();

  await logQuestion(page, untagged);
  await logQuestion(page, tagged);
  await page.getByRole("button", { name: "Tag with a concept" }).click();
  await page.getByRole("button", { name: title }).click();
  await expect(page.getByRole("link", { name: title })).toBeVisible();

  // The rail offers the concept as a filter alongside every other facet.
  await page.getByRole("button", { name: "Ask the bank" }).click();
  const panel = page.getByRole("complementary", { name: "Ask the bank" });
  await panel.getByRole("tab", { name: "Categories" }).click();
  await panel.getByRole("checkbox", { name: new RegExp(title) }).click();
  await panel.getByRole("button", { name: "Show 1 filter" }).click();

  await expect(page.getByRole("main").getByText(tagged)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole("main").getByText(untagged)).toBeHidden();

  // Untagging from the concept page leaves the question itself alone.
  await page.goto("/concepts");
  await page.getByText(title).click();
  await page.getByRole("button", { name: "Untag" }).click();
  await expect(page.getByText("Nothing tagged yet.")).toBeVisible();

  await page.goto("/bank");
  await expect(page.getByRole("main").getByText(tagged)).toBeVisible({ timeout: 10_000 });
});

test("deleting a concept keeps the questions", async ({ page }) => {
  const stamp = Date.now() % 100000;
  const title = `Disposable concept ${stamp}`;
  const question = `Survives deletion ${stamp} [e2e]`;

  await page.goto("/concepts");
  await page.getByRole("button", { name: "Write a concept" }).click();
  await page.getByLabel("The concept").fill(title);
  await page.getByRole("button", { name: "Add concept" }).click();
  await expect(page.getByText(title)).toBeVisible();

  await logQuestion(page, question);
  await page.getByRole("button", { name: "Tag with a concept" }).click();
  await page.getByRole("button", { name: title }).click();
  await expect(page.getByRole("link", { name: title })).toBeVisible();

  await page.getByRole("link", { name: title }).click();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Delete this concept" }).click();
  await expect(page).toHaveURL(/\/concepts$/);
  await expect(page.getByText(title)).toBeHidden();

  await page.goto("/bank");
  await expect(page.getByRole("main").getByText(question)).toBeVisible({ timeout: 10_000 });
});


test("questions can be tagged from the concept's own page, and show up there", async ({
  page,
}) => {
  const stamp = Date.now() % 100000;
  const title = `Tag from concept ${stamp}`;
  const question = `Tagged from the concept side ${stamp} [e2e]`;

  await logQuestion(page, question);

  await page.goto("/concepts");
  await page.getByRole("button", { name: /Write (a|your first) concept/ }).first().click();
  await page.getByLabel("The concept").fill(title);
  await page.getByRole("button", { name: "Add concept" }).click();
  await expect(page.getByText(title)).toBeVisible();
  await page.getByText(title).click();
  await expect(page).toHaveURL(/\/concepts\/[0-9a-f]{32}/);

  // Tag from here, rather than having to go and find the question.
  await expect(page.getByText("Nothing tagged yet.")).toBeVisible();
  await page.getByRole("button", { name: "Tag questions with this concept" }).click();
  await page.getByLabel("Search your questions").fill(`Tagged from the concept side ${stamp}`);
  await page.getByRole("button", { name: new RegExp(`Tagged from the concept side ${stamp}`) }).click();

  // It appears at the bottom of the concept immediately.
  await expect(page.getByText("Nothing tagged yet.")).toBeHidden();
  await expect(page.getByRole("main").getByText(question)).toBeVisible();

  // And the bank's card for that question now says which concept it is from.
  await page.goto("/bank");
  const card = page.getByRole("main").getByText(question).locator("xpath=ancestor::div[3]");
  await expect(card.getByText(title)).toBeVisible({ timeout: 10_000 });
});
