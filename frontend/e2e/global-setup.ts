import { randomBytes, randomUUID } from "node:crypto";
import { mkdirSync, unlinkSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { spawnSync } from "node:child_process";
import type { FullConfig } from "@playwright/test";

type E2ECredentials = {
  customerEmail: string;
  customerPassword: string;
  agentEmail: string;
  agentPassword: string;
};

function runPythonModule(config: FullConfig, module: string, extraEnv: Record<string, string>): void {
  const uvCommand = String(config.metadata.uvCommand ?? "uv");
  const backendDirectory = String(config.metadata.backendDirectory ?? resolve(process.cwd(), "../backend"));
  const result = spawnSync(uvCommand, ["run", "--locked", "python", "-m", module], {
    cwd: backendDirectory,
    env: { ...process.env, UV_CACHE_DIR: process.env.UV_CACHE_DIR ?? resolve(process.cwd(), "../.uv-cache"), ...extraEnv },
    encoding: "utf8",
    timeout: 60_000,
  });
  if (result.error || result.status !== 0) {
    throw new Error(`The local end-to-end account setup failed (${module}). ${result.stderr || result.error?.message || "Python command failed."}`);
  }
}

export default async function globalSetup(config: FullConfig): Promise<void> {
  const nonce = randomUUID().replaceAll("-", "");
  const credentials: E2ECredentials = {
    customerEmail: `caseflow-e2e-customer-${nonce}@example.com`,
    customerPassword: `E2E Customer ${randomBytes(18).toString("base64url")}`,
    agentEmail: `caseflow-e2e-agent-${nonce}@example.com`,
    agentPassword: `E2E Agent ${randomBytes(18).toString("base64url")}`,
  };
  const fixturePath = resolve(process.cwd(), ".playwright/e2e-fixtures.json");
  mkdirSync(resolve(process.cwd(), ".playwright"), { recursive: true });
  writeFileSync(fixturePath, JSON.stringify(credentials), { encoding: "utf8", mode: 0o600 });

  try {
    runPythonModule(config, "app.scripts.provision_staff", {
      CASEFLOW_STAFF_NAME: "Alex Support",
      CASEFLOW_STAFF_EMAIL: credentials.agentEmail,
      CASEFLOW_STAFF_PASSWORD: credentials.agentPassword,
      CASEFLOW_STAFF_ROLE: "agent",
    });
  } catch (error) {
    try {
      runPythonModule(config, "tests.e2e_support", {
        CASEFLOW_E2E_CUSTOMER_EMAIL: credentials.customerEmail,
        CASEFLOW_E2E_AGENT_EMAIL: credentials.agentEmail,
      });
    } catch (cleanupError) {
      throw new AggregateError([error, cleanupError], "End-to-end setup and cleanup both failed.", { cause: cleanupError });
    } finally {
      try {
        unlinkSync(fixturePath);
      } catch {
        // A failed setup may already have removed the credentials fixture.
      }
    }
    throw new Error("The end-to-end staff account could not be provisioned.", { cause: error });
  }
}
