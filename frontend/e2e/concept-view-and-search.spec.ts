import { expect, test, type Page } from "@playwright/test";

async function logQuestion(page: Page, fields: Record<string, string>) {
  await page.goto("/log");
  await page.getByLabel("Where it came from").fill(fields.source);
  await page.getByLabel("The question").fill(fields.question);
  await page.getByLabel("You put").fill(fields.yours);
  await page.getByLabel("The answer was").fill(fields.correct);
  await page.getByRole("button", { name: "Just log it" }).click();
  await expect(page).toHaveURL(/\/bank\/[0-9a-f]{32}/);
}

test("clicking a concept shows the concept itself, then its questions", async ({ page }) => {
  const stamp = Date.now() % 100000;
  const title = `Circumference gives the radius ${stamp}`;
  const question = `Circle area question ${stamp} [e2e]`;

  await logQuestion(page, {
    source: `Bluebook ${stamp}`,
    question,
    yours: "12π",
    correct: "36π",
  });

  await page.goto("/concepts");
  await page.getByRole("button", { name: /Write (a|your first) concept/ }).first().click();
  await page.getByLabel("The concept").fill(title);
  await page.getByLabel("In your own words").fill(`C = 2πr, so r = C / 2π. [${stamp}]`);
  await page.getByRole("button", { name: "Math", exact: true }).click();
  await page.getByRole("button", { name: "Add concept" }).click();
  await expect(page.getByText(title)).toBeVisible();

  await page.getByText(title).click();
  await page.getByRole("button", { name: "Tag questions with this concept" }).click();
  await page.getByLabel("Search your questions").fill(question);
  await page.getByRole("button", { name: new RegExp(`Circle area question ${stamp}`) }).click();
  await expect(page.getByRole("main").getByText(question)).toBeVisible();

  // Now the thing that was missing: filter by it from the rail.
  await page.getByRole("button", { name: "Ask the bank" }).click();
  const panel = page.getByRole("complementary", { name: "Ask the bank" });
  await panel.getByRole("tab", { name: "Categories" }).click();
  await panel.getByRole("button", { name: "Expand Math" }).click();
  await panel.getByRole("checkbox", { name: new RegExp(title) }).click();
  await panel.getByRole("button", { name: "Show 1 filter" }).click();

  const main = page.getByRole("main");
  // The concept, in the student's own words, above its questions. Matched as the
  // heading: the title also appears as the tag on the question's card, which is
  // correct and would otherwise make this ambiguous.
  await expect(main.getByRole("heading", { name: title })).toBeVisible({ timeout: 10_000 });
  await expect(main.getByText(`C = 2πr, so r = C / 2π. [${stamp}]`)).toBeVisible();
  await expect(main.getByText(/1 question filed under this concept/)).toBeVisible();
  await expect(main.getByText(question)).toBeVisible();
});

test("the rail can open a concept's own page, not only filter by it", async ({ page }) => {
  const stamp = Date.now() % 100000;
  const title = `Openable concept ${stamp}`;

  await page.goto("/concepts");
  await page.getByRole("button", { name: /Write (a|your first) concept/ }).first().click();
  await page.getByLabel("The concept").fill(title);
  await page.getByRole("button", { name: "Math", exact: true }).click();
  await page.getByRole("button", { name: "Add concept" }).click();
  await expect(page.getByText(title)).toBeVisible();

  await page.getByRole("button", { name: "Ask the bank" }).click();
  const panel = page.getByRole("complementary", { name: "Ask the bank" });
  await panel.getByRole("tab", { name: "Categories" }).click();
  // Concepts live under their section now, so open it first.
  await panel.getByRole("button", { name: "Expand Math" }).click();
  await panel.getByRole("link", { name: `Open ${title}` }).click();

  await expect(page).toHaveURL(/\/concepts\/[0-9a-f]{32}/);
  await expect(page.getByRole("main").getByText(title)).toBeVisible();
});

test("tagging finds a question by its source, its answer, or words in any order", async ({
  page,
}) => {
  const stamp = Date.now() % 100000;
  const title = `Search test concept ${stamp}`;
  const question = `A circle has a circumference of 12π. What is its area? ${stamp}`;

  await logQuestion(page, {
    source: `Bluebook Practice Test 4 ${stamp}`,
    question,
    yours: "12π",
    correct: `36π ${stamp}`,
  });

  await page.goto("/concepts");
  await page.getByRole("button", { name: /Write (a|your first) concept/ }).first().click();
  await page.getByLabel("The concept").fill(title);
  await page.getByRole("button", { name: "Math", exact: true }).click();
  await page.getByRole("button", { name: "Add concept" }).click();
  await expect(page.getByText(title)).toBeVisible();
  await page.getByText(title).click();
  await page.getByRole("button", { name: "Tag questions with this concept" }).click();

  const search = page.getByLabel("Search your questions");
  const hit = page.getByRole("button", { name: new RegExp(`circumference of 12`) });

  // By where it came from - found nothing before.
  await search.fill(`Bluebook ${stamp}`);
  await expect(hit).toBeVisible({ timeout: 10_000 });

  // By the answer - found nothing before.
  await search.fill(`36π ${stamp}`);
  await expect(hit).toBeVisible();

  // Words out of order and across fields - found nothing before.
  await search.fill(`area circle ${stamp}`);
  await expect(hit).toBeVisible();

  // And it still excludes what does not match.
  await search.fill(`definitely-not-in-this-bank-${stamp}`);
  await expect(hit).toBeHidden();
});
