import { defineConfig, devices } from "@playwright/test";

// Smoke test against the real server (FastAPI serving the built frontend + MySQL).
// Credentials come from E2E_USERNAME / E2E_PASSWORD (defaults match a dev .env).
const PORT = Number(process.env.E2E_PORT ?? 8011);
const baseURL = process.env.E2E_BASE_URL ?? `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: 0,
  reporter: [["list"]],
  use: { baseURL, trace: "retain-on-failure", locale: "en-US" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: `cd .. && .venv/bin/python -m app.cli serve --host 127.0.0.1 --port ${PORT}`,
        url: `${baseURL}/healthz`,
        reuseExistingServer: true,
        timeout: 60_000,
      },
});
