import { expect, test, type Page } from "@playwright/test";

async function logQuestion(page: Page, question: string) {
  await page.goto("/log");
  await page.getByLabel("The question").fill(question);
  await page.getByLabel("You put").fill("1");
  await page.getByLabel("The answer was").fill("2");
  await page.getByRole("button", { name: "Just log it" }).click();
  await expect(page).toHaveURL(/\/bank\/[0-9a-f]{32}/);
}

async function writeConcept(page: Page, title: string) {
  await page.goto("/concepts");
  await page.getByRole("button", { name: /Write (a|your first) concept/ }).first().click();
  await page.getByLabel("The concept").fill(title);
  await page.getByRole("button", { name: "Math", exact: true }).click();
  await page.getByRole("button", { name: "Add concept" }).click();
  await expect(page.getByText(title)).toBeVisible();
}

test("a concept with nothing tagged says so, rather than looking broken", async ({
  page,
}) => {
  const stamp = Date.now() % 100000;
  const title = `inverse trig ${stamp}`;

  await logQuestion(page, `Unrelated question ${stamp} [e2e]`);
  await writeConcept(page, title);

  await page.getByRole("button", { name: "Ask the bank" }).click();
  const panel = page.getByRole("complementary", { name: "Ask the bank" });
  await panel.getByRole("tab", { name: "Categories" }).click();
  await panel.getByRole("button", { name: "Expand Math" }).click();

  // The rail warns before you click it.
  const row = panel.getByRole("checkbox", { name: new RegExp(title) });
  await expect(row.getByText("nothing tagged")).toBeVisible();

  await row.click();
  await panel.getByRole("button", { name: "Show 1 filter" }).click();

  // And the bank names the concept instead of a generic "nothing matches".
  await expect(
    page.getByText(new RegExp(`Nothing is tagged with .${title}. yet`)),
  ).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole("link", { name: "Tag questions with it" })).toBeVisible();

  // That way out actually leads somewhere useful.
  await page.getByRole("link", { name: "Tag questions with it" }).click();
  await expect(page).toHaveURL(/\/concepts\/[0-9a-f]{32}/);
  await expect(page.getByRole("button", { name: "Tag questions with this concept" })).toBeVisible();
});

test("questions with no concept are findable and taggable", async ({ page }) => {
  const stamp = Date.now() % 100000;
  const title = `Taggable concept ${stamp}`;
  const question = `Needs a concept ${stamp} [e2e]`;

  await logQuestion(page, question);
  await writeConcept(page, title);

  // The dashboard says how many are unfiled.
  await page.goto("/");
  const nudge = page.getByRole("link", { name: /not filed under any concept/ });
  await expect(nudge).toBeVisible({ timeout: 10_000 });
  await nudge.click();

  await expect(page).toHaveURL(/tagged=0/);
  await expect(page.getByText("No concept yet")).toBeVisible();
  await expect(page.getByRole("main").getByText(question)).toBeVisible({ timeout: 10_000 });

  // Tag it, and it leaves the untagged view.
  await page.goto("/concepts");
  await page.getByText(title).click();
  await page.getByRole("button", { name: "Tag questions with this concept" }).click();
  await page.getByLabel("Search your questions").fill(question);
  await page.getByRole("button", { name: new RegExp(`Needs a concept ${stamp}`) }).click();
  await expect(page.getByRole("main").getByText(question)).toBeVisible();

  await page.goto("/bank?tagged=0");
  await expect(page.getByRole("main").getByText(question)).toBeHidden();
});
