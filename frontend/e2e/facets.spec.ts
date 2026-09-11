import { expect, test, type Page } from "@playwright/test";


/** Logs a question and hand-sets the facets, so the test does not depend on what
 *  the analyzer happened to choose. */
async function logWith(
  page: Page,
  question: string,
  section: "Math" | "Reading & Writing",
  facets: { urgency: string; topic: string; errorType: string },
) {
  await page.goto("/log");
  await page.getByRole("button", { name: section, exact: true }).click();
  await page.getByLabel("The question").fill(question);
  await page.getByLabel("You put").fill("1");
  await page.getByLabel("The answer was").fill("2");
  await page.getByRole("button", { name: "Just log it" }).click();
  await expect(page).toHaveURL(/\/bank\/[0-9a-f]{32}/);

  await page.getByRole("button", { name: "Write it myself" }).click();
  await page.getByLabel("How urgent").selectOption(facets.urgency);
  await page.getByLabel("Why you got it wrong").selectOption(facets.errorType);
  await page.getByLabel("Topic").fill(facets.topic);
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText(facets.topic).first()).toBeVisible();
}

test("topics live under their section, and four facets narrow each other", async ({
  page,
}) => {
  const stamp = Date.now() % 10000;
  const wanted = `Facet target ${stamp} [e2e]`;
  const wrongTopic = `Facet wrong topic ${stamp} [e2e]`;
  const wrongSection = `Facet wrong section ${stamp} [e2e]`;

  await logWith(page, wanted, "Math", {
    urgency: "very_important",
    topic: `math fundamentals ${stamp}`,
    errorType: "concept_gap",
  });
  await logWith(page, wrongTopic, "Math", {
    urgency: "very_important",
    topic: `circles ${stamp}`,
    errorType: "concept_gap",
  });
  await logWith(page, wrongSection, "Reading & Writing", {
    urgency: "very_important",
    topic: `math fundamentals ${stamp}`,
    errorType: "concept_gap",
  });

  await page.getByRole("button", { name: "Ask the bank" }).click();
  const panel = page.getByRole("complementary", { name: "Ask the bank" });
  await panel.getByRole("tab", { name: "Categories" }).click();

  // A topic is not visible until its own section is opened.
  await expect(panel.getByText(`math fundamentals ${stamp}`)).toBeHidden();
  await panel.getByRole("button", { name: "Expand Math" }).click();
  await expect(panel.getByText(`math fundamentals ${stamp}`)).toBeVisible();
  await expect(panel.getByText(`circles ${stamp}`)).toBeVisible();

  // Four facets at once: section, topic, slot, urgency.
  await panel.getByRole("checkbox", { name: /^Math/ }).click();
  await panel.getByRole("checkbox", { name: new RegExp(`math fundamentals ${stamp}`) }).click();
  await panel.getByRole("checkbox", { name: /Concept gap/ }).click();
  await panel.getByRole("checkbox", { name: /Very important/ }).click();
  await panel.getByRole("button", { name: "Show 4 filters" }).click();

  await expect(page).toHaveURL(/\/bank\?/);
  const article = page.locator("main");
  await expect(article.getByText(wanted)).toBeVisible({ timeout: 10_000 });
  // The two that differ in exactly one facet are excluded.
  await expect(article.getByText(wrongTopic)).toBeHidden();
  await expect(article.getByText(wrongSection)).toBeHidden();
});

test("a filtered bank is a link, and each filter can be peeled off", async ({ page }) => {
  const stamp = Date.now() % 10000;
  const question = `Peelable ${stamp} [e2e]`;
  await logWith(page, question, "Math", {
    urgency: "fundamental",
    topic: `peel ${stamp}`,
    errorType: "formula_error",
  });

  // Straight to a multi-facet URL: the filters are in the address, not in memory.
  await page.goto(`/bank?section=math&urgency=fundamental&topic=${encodeURIComponent(`peel ${stamp}`)}`);
  await expect(page.getByText(question)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("Fundamental concept").first()).toBeVisible();

  // Removing a filter widens the result rather than resetting everything.
  await page.getByRole("button", { name: "Remove filter" }).first().click();
  await expect(page).toHaveURL(/urgency=fundamental/);
  await expect(page.getByText(question)).toBeVisible();

  await page.getByRole("button", { name: "Clear all" }).click();
  await expect(page).toHaveURL(/\/bank$/);
});

test("a combination that matches nothing explains why", async ({ page }) => {
  await page.goto("/bank?section=math&section=reading_writing&urgency=fundamental&topic=nothing-has-this-topic");

  await expect(page.getByText("Nothing matches all of those.")).toBeVisible({
    timeout: 10_000,
  });
});
