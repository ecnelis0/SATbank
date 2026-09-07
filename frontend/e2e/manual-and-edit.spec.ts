import { expect, test } from "@playwright/test";

function uniqueQuestion() {
  return `A circle has circumference ${Date.now() % 1000}π. What is its area? [e2e]`;
}

async function logByHand(page: import("@playwright/test").Page, question: string) {
  await page.goto("/log");
  await page.getByLabel("The question").fill(question);
  await page.getByLabel("You put").fill("12");
  await page.getByLabel("The answer was").fill("36");
  await page.getByRole("button", { name: "Just log it" }).click();
  await expect(page).toHaveURL(/\/bank\/[0-9a-f]{32}/);
}

test("a question logged by hand waits to be asked, then debriefs on request", async ({
  page,
}) => {
  await logByHand(page, uniqueQuestion());

  // Nothing was invented on the student's behalf.
  await expect(page.getByText(/No debrief yet/)).toBeVisible();
  await expect(page.getByText("WHY YOU GOT IT WRONG")).toBeHidden();
  // But the ladder is running regardless.
  await expect(
    page.getByRole("list", { name: "Review schedule" }).getByRole("listitem"),
  ).toHaveCount(5);

  await page.getByRole("button", { name: "Ask the AI to debrief this" }).click();

  await expect(page.getByText("WHY YOU GOT IT WRONG")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("REMEMBER")).toBeVisible();
});

test("the student can write the analysis themselves and it files like any other", async ({
  page,
}) => {
  await logByHand(page, uniqueQuestion());

  await page.getByRole("button", { name: "Write it myself" }).click();
  await page.getByLabel("Why you got it wrong").selectOption("time_pressure_guess");
  await page.getByLabel("Topic").fill("circles");
  await page.getByLabel("Remember").fill("Circumference gives the radius first.");
  await page.getByRole("button", { name: "Save" }).click();

  await expect(page.getByText("Circumference gives the radius first.")).toBeVisible();
  await expect(page.getByText("Written by you.")).toBeVisible();

  // It is a real slot now, browsable from the bank like an AI-written one.
  await page.goto("/bank?error_type=time_pressure_guess");
  await expect(page.getByText("Guessed under time pressure").first()).toBeVisible();
});

test("every part of the question itself is editable", async ({ page }) => {
  await logByHand(page, uniqueQuestion());

  await page.getByRole("button", { name: "Edit question" }).click();
  await page.getByLabel("The question").fill("Rewritten question text [e2e]");
  await page.getByLabel("Where it came from").fill("Khan Academy drill");
  await page.getByLabel("Answer choices").fill("6π\n12π\n36π");
  await page.getByLabel("You put").fill("6π");
  await page.getByLabel("The answer was").fill("36π");
  await page.getByLabel("What happened?").fill("Forgot to halve the diameter.");
  await page.getByRole("button", { name: "Save" }).click();

  await expect(page.getByText("Rewritten question text [e2e]")).toBeVisible();
  await expect(page.getByText("Khan Academy drill")).toBeVisible();
  await expect(page.getByText("Forgot to halve the diameter.")).toBeVisible();
  await expect(page.getByText("36π").first()).toBeVisible();

  // And it survives a reload - it was saved, not just re-rendered.
  await page.reload();
  await expect(page.getByText("Rewritten question text [e2e]")).toBeVisible();
});
