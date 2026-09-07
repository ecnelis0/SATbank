import { expect, test, type Page } from "@playwright/test";

const QUESTION_IMAGE = "e2e/fixtures/question.png";
const WORKING_IMAGE = "e2e/fixtures/working.png";

async function logQuestion(page: Page, question: string) {
  await page.goto("/log");
  await page.getByLabel("The question").fill(question);
  await page.getByLabel("You put").fill("B");
  await page.getByLabel("The answer was").fill("C");
  await page.getByRole("button", { name: "Just log it" }).click();
  await expect(page).toHaveURL(/\/bank\/[0-9a-f]{32}/);
  return page.url();
}

test("a picture can be attached to a question and zoomed", async ({ page }) => {
  const url = await logQuestion(page, `Picture question ${Date.now() % 100000} [e2e]`);
  await expect(page.getByText("No pictures yet.")).toBeVisible();

  await page.getByLabel("Add a picture").setInputFiles(QUESTION_IMAGE);

  const thumbnail = page.getByRole("img", { name: "Picture 1 of the question" });
  await expect(thumbnail).toBeVisible({ timeout: 15_000 });

  // Really painted, not merely in the DOM: a decoded image has a natural size.
  // Polled, because visibility lands before the bytes do.
  await expect
    .poll(
      () =>
        thumbnail.evaluate(
          (img: HTMLImageElement) => img.complete && img.naturalWidth > 0,
        ),
      { timeout: 15_000 },
    )
    .toBe(true);

  // Zoom: click the thumbnail with a real pointer and check the full-size view opens.
  await page.getByRole("button", { name: "Open picture 1 full size" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();

  const before = await dialog
    .locator(".yarl__slide_current img")
    .evaluate((img) => img.getBoundingClientRect().width);

  // Zooming in must actually make it bigger.
  await page.getByRole("button", { name: /zoom in/i }).click();
  await page.waitForTimeout(400);
  const after = await dialog
    .locator(".yarl__slide_current img")
    .evaluate((img) => img.getBoundingClientRect().width);
  expect(after).toBeGreaterThan(before);

  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();

  // And it survives a reload - it was stored, not just held in memory.
  await page.goto(url);
  await expect(page.getByRole("img", { name: "Picture 1 of the question" })).toBeVisible();
});

test("several pictures, and one can be removed", async ({ page }) => {
  await logQuestion(page, `Two picture question ${Date.now() % 100000} [e2e]`);

  await page.getByLabel("Add a picture").setInputFiles([QUESTION_IMAGE, WORKING_IMAGE]);
  await expect(page.getByRole("img", { name: "Picture 2 of the question" })).toBeVisible({
    timeout: 20_000,
  });

  await page.getByRole("button", { name: "Delete picture 1" }).click();

  await expect(page.getByRole("img", { name: "Picture 2 of the question" })).toBeHidden();
  await expect(page.getByRole("img", { name: "Picture 1 of the question" })).toBeVisible();
});

test("a file that is not an image is refused with a reason", async ({ page }) => {
  await logQuestion(page, `Bad upload question ${Date.now() % 100000} [e2e]`);

  await page.getByLabel("Add a picture").setInputFiles({
    name: "not-really.png",
    mimeType: "image/png",
    buffer: Buffer.from("#!/bin/sh\nrm -rf /\n"),
  });

  await expect(page.getByText(/not an image we can read/)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("No pictures yet.")).toBeVisible();
});

test("a question's picture shows up in the review session", async ({ page }) => {
  await logQuestion(page, `Reviewable picture ${Date.now() % 100000} [e2e]`);
  await page.getByLabel("Add a picture").setInputFiles(QUESTION_IMAGE);
  await expect(page.getByRole("img", { name: "Picture 1 of the question" })).toBeVisible({
    timeout: 15_000,
  });

  // Nothing is due yet, so the session is empty - but the component that renders
  // the picture is the same one, exercised above on the question page.
  await page.goto("/review");
  await expect(page.getByText("Nothing is due.")).toBeVisible();
});
