import { expect, test } from "@playwright/test";

const USER = process.env.E2E_USERNAME ?? "admin";
const PASSWORD = process.env.E2E_PASSWORD ?? "";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("tuc.lang", "en"));
});

test("unauthenticated users are sent to login and bad passwords are rejected", async ({ page }) => {
  await page.goto("/files");
  await expect(page).toHaveURL(/\/login/);
  await page.getByLabel("Username").fill(USER);
  await page.getByLabel("Password").fill("definitely-wrong");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert")).toContainText("Invalid username or password");
});

test("login → overview → files → file detail", async ({ page, isMobile }) => {
  test.skip(!PASSWORD, "Set E2E_PASSWORD to the dashboard password");
  await page.goto("/login");
  await page.getByLabel("Username").fill(USER);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page.getByRole("heading", { name: "Overview", level: 1 })).toBeVisible();
  await expect(page.getByText("Total files", { exact: true })).toBeVisible();
  await expect(page.getByText("System health", { exact: true })).toBeVisible();

  if (isMobile) {
    await page.getByRole("button", { name: "Open navigation" }).click();
  }
  await page.getByRole("link", { name: "Files" }).first().click();
  await expect(page.getByRole("heading", { name: "Files", level: 1 })).toBeVisible();
  await expect(page.getByPlaceholder("Search name, caption, id or hash…")).toBeVisible();

  const firstRow = isMobile ? page.locator("main ul li button").first() : page.locator("main tbody tr").first();
  if (await firstRow.count()) {
    await firstRow.click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByRole("tab", { name: "Processing timeline" })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toBeHidden();
  }

  // Arabic switches the whole layout to RTL.
  await page.getByRole("button", { name: "Language" }).click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByRole("heading", { name: "الملفات", level: 1 })).toBeVisible();
});
