import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig } from "@playwright/test";

const backendDirectory = resolve(process.cwd(), "../backend");
const localUv = resolve(process.cwd(), "../.uv-venv/Scripts/uv.exe");

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  globalTeardown: "./e2e/global-teardown.ts",
  outputDir: "./test-results/playwright",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  forbidOnly: Boolean(process.env.CI),
  use: {
    baseURL: process.env.CASEFLOW_E2E_BASE_URL ?? "http://localhost:8000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  metadata: {
    backendDirectory,
    uvCommand: process.env.CASEFLOW_UV_BIN ?? (existsSync(localUv) ? localUv : "uv"),
  },
});
