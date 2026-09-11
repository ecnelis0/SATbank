import { readFileSync } from "node:fs";

import { expect, test, type Locator, type Page } from "@playwright/test";

/** A real drag-and-drop: build a DataTransfer in the page and drop it on the zone. */
async function dropFile(page: Page, zone: Locator, path: string, name: string) {
  const bytes = Array.from(readFileSync(path));
  const dataTransfer = await page.evaluateHandle(
    ({ bytes, name }) => {
      const transfer = new DataTransfer();
      transfer.items.add(
        new File([new Uint8Array(bytes)], name, { type: "image/png" }),
      );
      return transfer;
    },
    { bytes, name },
  );
  await zone.dispatchEvent("drop", { dataTransfer });
}

test("a picture can be dragged onto the log form and is saved with the question", async ({
  page,
}) => {
  const question = `Dropped at log time ${Date.now() % 100000} [e2e]`;

  await page.goto("/log");
  await page.getByLabel("The question").fill(question);
  await page.getByLabel("You put").fill("7");
  await page.getByLabel("The answer was").fill("5");

  const zone = page.getByLabel("Drag a screenshot here, or click to choose");
  await dropFile(page, zone, "e2e/fixtures/question.png", "dropped.png");

  // It previews before the question exists, and nothing has been uploaded yet.
  await expect(page.getByRole("img", { name: "Picture 1 to upload" })).toBeVisible();

  await page.getByRole("button", { name: "Just log it" }).click();
  await expect(page).toHaveURL(/\/bank\/[0-9a-f]{32}/);

  // And it is on the saved question, decoded, not merely in the DOM.
  const saved = page.getByRole("img", { name: "Picture 1 of the question" });
  await expect(saved).toBeVisible({ timeout: 20_000 });
  await expect
    .poll(
      () =>
        saved.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0),
      { timeout: 15_000 },
    )
    .toBe(true);

  await page.reload();
  await expect(page.getByRole("img", { name: "Picture 1 of the question" })).toBeVisible();
});

test("a dropped picture can be taken back off before the question is saved", async ({
  page,
}) => {
  await page.goto("/log");
  const zone = page.getByLabel("Drag a screenshot here, or click to choose");
  await dropFile(page, zone, "e2e/fixtures/question.png", "oops.png");
  await expect(page.getByRole("img", { name: "Picture 1 to upload" })).toBeVisible();

  await page.getByRole("button", { name: "Remove picture 1" }).click();

  await expect(page.getByRole("img", { name: "Picture 1 to upload" })).toBeHidden();
});

test("a diagram can be dragged onto a new concept", async ({ page }) => {
  const title = `Dropped diagram concept ${Date.now() % 100000}`;

  await page.goto("/concepts");
  await page.getByRole("button", { name: /Write (a|your first) concept/ }).first().click();
  await page.getByLabel("The concept").fill(title);

  const zone = page.getByLabel("Drag a screenshot here, or click to choose");
  await dropFile(page, zone, "e2e/fixtures/working.png", "figure.png");
  await expect(page.getByRole("img", { name: "Picture 1 to upload" })).toBeVisible();

  await page.getByRole("button", { name: "Math", exact: true }).click();
  await page.getByRole("button", { name: "Add concept" }).click();
  await expect(page.getByText(title)).toBeVisible();

  await page.getByText(title).click();
  await expect(page).toHaveURL(/\/concepts\/[0-9a-f]{32}/);
  const diagram = page.getByRole("img", { name: "Diagram 1 of the concept" });
  await expect(diagram).toBeVisible({ timeout: 20_000 });
  await expect
    .poll(
      () =>
        diagram.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0),
      { timeout: 15_000 },
    )
    .toBe(true);
});

test("a diagram can be dragged onto an existing concept, and zoomed", async ({ page }) => {
  const title = `Existing concept diagram ${Date.now() % 100000}`;

  await page.goto("/concepts");
  await page.getByRole("button", { name: /Write (a|your first) concept/ }).first().click();
  await page.getByLabel("The concept").fill(title);
  await page.getByRole("button", { name: "Math", exact: true }).click();
  await page.getByRole("button", { name: "Add concept" }).click();
  await expect(page.getByText(title)).toBeVisible();

  await page.getByText(title).click();
  await expect(page.getByText("No diagrams yet.")).toBeVisible();

  const zone = page.getByLabel("Drag pictures here, or click to choose");
  await dropFile(page, zone, "e2e/fixtures/question.png", "figure.png");
  await expect(page.getByRole("img", { name: "Diagram 1 of the concept" })).toBeVisible({
    timeout: 20_000,
  });

  await page.getByRole("button", { name: "Open diagram 1 full size" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();

  const before = await dialog
    .locator(".yarl__slide_current img")
    .evaluate((img) => img.getBoundingClientRect().width);
  await page.getByRole("button", { name: /zoom in/i }).click();
  await page.waitForTimeout(400);
  const after = await dialog
    .locator(".yarl__slide_current img")
    .evaluate((img) => img.getBoundingClientRect().width);
  expect(after).toBeGreaterThan(before);
});
