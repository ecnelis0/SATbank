import { defineConfig } from "@playwright/test";

const WEB_PORT = 3401;
const API_PORT = 8001;

/** The e2e stack runs on its own ports and its own database file, so a local
 *  dev session (and its data) is never touched by a test run. */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "line" : "list",
  use: {
    // localhost, not 127.0.0.1: Next blocks dev resources for any other host,
    // which leaves the page unhydrated and every assertion mystifying.
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `uv run uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT}`,
      cwd: "../backend",
      url: `http://127.0.0.1:${API_PORT}/health`,
      env: { DATABASE_URL: "sqlite+aiosqlite:///./e2e.db", AI_PROVIDER: "stub" },
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      // A production build, not `next dev`: Next refuses a second dev server in the
      // same directory, and the built bundle is what actually ships.
      command: `npm run build && npm run start -- --port ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}`,
      env: { NEXT_PUBLIC_API_URL: `http://127.0.0.1:${API_PORT}` },
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
    },
  ],
});
