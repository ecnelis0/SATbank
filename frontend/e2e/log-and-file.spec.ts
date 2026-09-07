import { expect, test } from "@playwright/test";

/** Unique per run, so a repeated run never matches an earlier one's question. */
function uniqueQuestion() {
  return `If 4x + ${Date.now() % 100} = 40, what is x? [e2e]`;
}

test("logging a miss analyses it, files it in a slot, and arms the full ladder", async ({
  page,
}) => {
  const question = uniqueQuestion();

  await page.goto("/log");
  await page.getByRole("button", { name: "Math", exact: true }).click();
  await page.getByLabel("Where it came from").fill("Bluebook Practice Test 4, Q17");
  await page.getByLabel("The question").fill(question);
  await page.getByLabel("Answer choices").fill("3\n5\n7\n15");
  await page.getByLabel("You put").fill("7");
  await page.getByLabel("The answer was").fill("5");
  await page.getByLabel("What happened?").fill("Stopped one step early.");
  await page.getByRole("button", { name: "Log this miss" }).click();

  // Landing on the question's own page is what tells the student it was saved.
  await expect(page).toHaveURL(/\/bank\/[0-9a-f]{32}/);
  await expect(page.getByText(question)).toBeVisible();

  // The analysis arrives from the background task moments later.
  await expect(page.getByText("WHY YOU GOT IT WRONG")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("REMEMBER")).toBeVisible();

  // All five rungs, none of them answered yet, the first one an hour out.
  const rungs = page.getByRole("list", { name: "Review schedule" }).getByRole("listitem");
  await expect(rungs).toHaveCount(5);
  await expect(rungs.first()).toContainText("1 hour");
  await expect(rungs.first()).toContainText("in ");
  await expect(rungs.last()).toContainText("1 month");
});

test("a freshly logged miss is findable in the bank", async ({ page }) => {
  const question = uniqueQuestion();

  await page.goto("/log");
  await page.getByLabel("The question").fill(question);
  await page.getByLabel("You put").fill("12");
  await page.getByLabel("The answer was").fill("9");
  await page.getByRole("button", { name: "Log this miss" }).click();
  await expect(page).toHaveURL(/\/bank\/[0-9a-f]{32}/);

  await page.goto("/bank");
  await page.getByLabel("Search the questions").fill(question.slice(0, 20));

  await expect(page.getByText(question)).toBeVisible({ timeout: 10_000 });
});

test("the review page says so when nothing is due yet", async ({ page }) => {
  // Everything logged in this run is an hour away from its first rung.
  await page.goto("/review");

  await expect(page.getByText("Nothing is due.")).toBeVisible({ timeout: 10_000 });
});
