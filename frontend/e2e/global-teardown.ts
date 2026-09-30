import { unlinkSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { spawnSync } from "node:child_process";
import type { FullConfig } from "@playwright/test";

type E2ECredentials = {
  customerEmail: string;
  agentEmail: string;
};

export default async function globalTeardown(config: FullConfig): Promise<void> {
  const fixturePath = resolve(process.cwd(), ".playwright/e2e-fixtures.json");
  try {
    let credentials: E2ECredentials;
    try {
      credentials = JSON.parse(readFileSync(fixturePath, "utf8")) as E2ECredentials;
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return;
      throw error;
    }
    const result = spawnSync(String(config.metadata.uvCommand ?? "uv"), ["run", "--locked", "python", "-m", "tests.e2e_support"], {
      cwd: String(config.metadata.backendDirectory ?? resolve(process.cwd(), "../backend")),
      env: {
        ...process.env,
        UV_CACHE_DIR: process.env.UV_CACHE_DIR ?? resolve(process.cwd(), "../.uv-cache"),
        CASEFLOW_E2E_CUSTOMER_EMAIL: credentials.customerEmail,
        CASEFLOW_E2E_AGENT_EMAIL: credentials.agentEmail,
      },
      encoding: "utf8",
      timeout: 60_000,
    });
    if (result.error || result.status !== 0) {
      throw new Error(`The local end-to-end account cleanup failed. ${result.stderr || result.error?.message || "Python command failed."}`);
    }
  } finally {
    try {
      unlinkSync(fixturePath);
    } catch {
      // A failed global setup may not have written the fixture file.
    }
  }
}
