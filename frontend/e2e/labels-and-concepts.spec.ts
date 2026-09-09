import { expect, test, type Page } from "@playwright/test";

async function writeConcept(page: Page, title: string, section?: "math" | "reading_writing") {
  await page.goto("/concepts");
  await page.getByRole("button", { name: /Write (a|your first) concept/ }).first().click();
  await page.getByLabel("The concept").fill(title);
  if (section) await page.getByLabel("Section").selectOption(section);
  await page.getByRole("button", { name: "Add concept" }).click();
  await expect(page.getByText(title)).toBeVisible();
}

test("a question can be labelled and filed under a concept while logging", async ({
  page,
}) => {
  const stamp = Date.now() % 100000;
  const concept = `Isolate before dividing ${stamp}`;
  const question = `Labelled at log time ${stamp} [e2e]`;

  await writeConcept(page, concept, "math");

  await page.goto("/log");
  await page.getByLabel("The question").fill(question);
  await page.getByLabel("You put").fill("7");
  await page.getByLabel("The answer was").fill("5");

  // A label of my own, typed and entered.
  await page.getByLabel("Add a label").fill(`sloppy ${stamp}`);
  await page.getByLabel("Add a label").press("Enter");
  // Enter must add the label, not submit the form.
  await expect(page).toHaveURL(/\/log$/);
  // And one of the offered ones.
  await page.getByRole("button", { name: /by mistake/ }).click();

  await page.getByRole("button", { name: new RegExp(concept) }).click();
  await page.getByRole("button", { name: "Just log it" }).click();
  await expect(page).toHaveURL(/\/bank\/[0-9a-f]{32}/);

  // Both labels and the concept are on the saved question.
  await expect(page.getByRole("link", { name: concept })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("link", { name: concept })).toBeVisible();

  // The label is now offered back to the next question.
  await page.goto("/log");
  await expect(page.getByRole("button", { name: new RegExp(`sloppy ${stamp}`) })).toBeVisible({
    timeout: 10_000,
  });
});

test("concepts are grouped into Math and Reading & Writing", async ({ page }) => {
  const stamp = Date.now() % 100000;
  const mathConcept = `Math concept ${stamp}`;
  const englishConcept = `English concept ${stamp}`;

  await writeConcept(page, mathConcept, "math");
  await writeConcept(page, englishConcept, "reading_writing");

  await page.goto("/concepts");

  const math = page.getByRole("button", { name: /^Math/ });
  const english = page.getByRole("button", { name: /^Reading & Writing/ });
  await expect(math).toBeVisible();
  await expect(english).toBeVisible();

  // Open by default, each holding its own concepts and not the other's.
  await expect(page.getByRole("link", { name: new RegExp(mathConcept) })).toBeVisible();
  await expect(page.getByRole("link", { name: new RegExp(englishConcept) })).toBeVisible();

  // Collapsing one hides only its own.
  await math.click();
  await expect(page.getByRole("link", { name: new RegExp(mathConcept) })).toBeHidden();
  await expect(page.getByRole("link", { name: new RegExp(englishConcept) })).toBeVisible();

  await math.click();
  await expect(page.getByRole("link", { name: new RegExp(mathConcept) })).toBeVisible();
});


test("labels can be added and removed from a question already in the bank", async ({
  page,
}) => {
  const stamp = Date.now() % 100000;
  const question = `Relabel me later ${stamp} [e2e]`;

  // Logged with no labels at all.
  await page.goto("/log");
  await page.getByLabel("The question").fill(question);
  await page.getByLabel("You put").fill("1");
  await page.getByLabel("The answer was").fill("2");
  await page.getByRole("button", { name: "Log it and ask the AI" }).click();
  await expect(page).toHaveURL(/\/bank\/[0-9a-f]{32}/);
  const url = page.url();

  // The question page has its own label picker - this is what was missing.
  await expect(page.getByText("Your labels")).toBeVisible();
  await page.getByLabel("Add a label").fill(`invented ${stamp}`);
  await page.getByLabel("Add a label").press("Enter");
  await expect(page.getByRole("button", { name: `Remove label invented ${stamp}` })).toBeVisible();

  // One of the offered ones too.
  await page.getByRole("button", { name: /^by mistake/ }).click();
  await expect(page.getByRole("button", { name: "Remove label by mistake" })).toBeVisible();

  // It really saved.
  await page.reload();
  await expect(page.getByRole("button", { name: `Remove label invented ${stamp}` })).toBeVisible();

  // Removing one saves too.
  await page.getByRole("button", { name: "Remove label by mistake" }).click();
  await page.reload();
  await expect(page.getByRole("button", { name: "Remove label by mistake" })).toBeHidden();
  await expect(page.getByRole("button", { name: `Remove label invented ${stamp}` })).toBeVisible();

  // And relabelling has not locked the AI out of its own analysis.
  await page.goto(url);
  await page.getByRole("button", { name: "Re-run the AI" }).click();
  await expect(page.getByText("WHY YOU GOT IT WRONG")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("button", { name: `Remove label invented ${stamp}` })).toBeVisible();
});
