import { expect, test } from "@playwright/test";

test("the AI rates how urgent a miss is, and the student can overrule it", async ({
  page,
}) => {
  const question = `Urgency check ${Date.now() % 10000} [e2e]`;

  await page.goto("/log");
  await page.getByLabel("The question").fill(question);
  await page.getByLabel("You put").fill("7");
  await page.getByLabel("The answer was").fill("5");
  await page.getByRole("button", { name: "Log it and ask the AI" }).click();
  await expect(page).toHaveURL(/\/bank\/[0-9a-f]{32}/);

  // The analyzer rates it; "Important" is what a careless slip earns.
  await expect(page.getByText("Important", { exact: true })).toBeVisible({
    timeout: 15_000,
  });

  await page.getByRole("button", { name: "Edit the debrief" }).click();
  await page.getByLabel("How urgent").selectOption("fundamental");
  await page.getByRole("button", { name: "Save" }).click();

  await expect(page.getByText("Fundamental concept")).toBeVisible();

  // And it is a filter, so "what do I fix first" is one click from the dashboard.
  await page.goto("/bank?urgency=fundamental");
  await expect(page.getByText(question)).toBeVisible({ timeout: 10_000 });

  await page.goto("/bank?urgency=important");
  await expect(page.getByText(question)).toBeHidden();
});

test("the dashboard leads with what to fix first", async ({ page }) => {
  await page.goto("/log");
  await page.getByLabel("The question").fill(`Dashboard urgency ${Date.now()} [e2e]`);
  await page.getByLabel("You put").fill("1");
  await page.getByLabel("The answer was").fill("2");
  await page.getByRole("button", { name: "Log it and ask the AI" }).click();
  await expect(page).toHaveURL(/\/bank\/[0-9a-f]{32}/);

  await page.goto("/");

  const section = page.locator("section", { hasText: "What to fix first" });
  await expect(section.getByText("Fundamental concept")).toBeVisible({ timeout: 10_000 });
  await expect(section.getByText("Very important")).toBeVisible();
  await expect(section.getByText("Important", { exact: true })).toBeVisible();
});


test("importance can be set while logging, and the AI does not overrule it", async ({
  page,
}) => {
  const question = `Urgency at log time ${Date.now() % 10000} [e2e]`;

  await page.goto("/log");
  await page.getByLabel("The question").fill(question);
  await page.getByLabel("You put").fill("60");
  await page.getByLabel("The answer was").fill("30");
  await page.getByRole("button", { name: "Fundamental concept" }).click();
  // Ask the AI too: the point is that it analyses everything else and leaves this.
  await page.getByRole("button", { name: "Log it and ask the AI" }).click();
  await expect(page).toHaveURL(/\/bank\/[0-9a-f]{32}/);

  await expect(page.getByText("WHY YOU GOT IT WRONG")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Fundamental concept")).toBeVisible();
  await expect(page.getByText("your call")).toBeVisible();
});

test("leaving it to the AI still gets an urgency", async ({ page }) => {
  const question = `Urgency left to the AI ${Date.now() % 10000} [e2e]`;

  await page.goto("/log");
  await page.getByLabel("The question").fill(question);
  await page.getByLabel("You put").fill("7");
  await page.getByLabel("The answer was").fill("5");
  await page.getByRole("button", { name: "Log it and ask the AI" }).click();
  await expect(page).toHaveURL(/\/bank\/[0-9a-f]{32}/);

  await expect(page.getByText("WHY YOU GOT IT WRONG")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("your call")).toBeHidden();
});
