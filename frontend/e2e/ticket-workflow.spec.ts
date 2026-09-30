import { mkdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";

type E2ECredentials = {
  customerEmail: string;
  customerPassword: string;
  agentEmail: string;
  agentPassword: string;
};

const credentials = JSON.parse(
  readFileSync(resolve(process.cwd(), ".playwright/e2e-fixtures.json"), "utf8"),
) as E2ECredentials;
const reference = Math.random().toString(36).slice(2, 8).toUpperCase();
const subject = `E2E support request ${reference}`;
const privateNote = `Private QA note ${reference} must stay hidden from customers.`;
const publicReply = `Public QA update ${reference}: support has picked this up.`;

test("read-only demo renders without requesting live ticket data", async ({ page }) => {
  const ticketRequests: string[] = [];
  page.on("request", (request) => {
    if (/\/api\/v1\/tickets(?:\/|\?|$)/.test(request.url())) ticketRequests.push(request.url());
  });
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.goto("/demo");
  await expect(page.getByRole("heading", { name: "A clearer view of every request." })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Profile changes are not appearing yet" })).toBeVisible();
  await expect(page.getByText("This preview is read-only.")).toBeVisible();
  expect(ticketRequests).toEqual([]);
  const screenshotPath = resolve(process.cwd(), "../docs/screenshots/caseflow-demo.png");
  mkdirSync(resolve(process.cwd(), "../docs/screenshots"), { recursive: true });
  await page.screenshot({ path: screenshotPath, fullPage: true });
});

test("customer and support complete the ticket lifecycle with private-note isolation", async ({ browser }) => {
  const customerContext = await browser.newContext();
  const customerPage = await customerContext.newPage();
  await customerPage.goto("/register");
  await customerPage.getByLabel("Full name").fill("Jordan Example");
  await customerPage.getByLabel("Email address").fill(credentials.customerEmail);
  await customerPage.locator("#password").fill(credentials.customerPassword);
  await customerPage.getByLabel("Confirm password").fill(credentials.customerPassword);
  await customerPage.getByRole("button", { name: "Create account" }).click();
  await expect(customerPage.getByRole("heading", { name: "Your overview" })).toBeVisible();

  await customerPage.getByRole("link", { name: /New request/ }).first().click();
  await customerPage.getByLabel("Subject").fill(subject);
  await customerPage.getByLabel("Category").selectOption("technical");
  await customerPage.getByLabel("What happened?").fill(
    "A synthetic end-to-end request for verifying ticket ownership, replies and support-only notes.",
  );
  await customerPage.getByRole("button", { name: "Submit request" }).click();
  await expect(customerPage.getByRole("heading", { name: subject })).toBeVisible();
  const customerTicketUrl = customerPage.url();

  const agentContext = await browser.newContext();
  const agentPage = await agentContext.newPage();
  await agentPage.goto("/login");
  await agentPage.getByLabel("Email address").fill(credentials.agentEmail);
  await agentPage.getByLabel("Password").fill(credentials.agentPassword);
  await agentPage.getByRole("button", { name: "Sign in" }).click();
  await expect(agentPage.getByRole("heading", { name: "Shared queue" })).toBeVisible();
  await agentPage.getByRole("link", { name: new RegExp(subject) }).click();
  await agentPage.getByRole("button", { name: "Claim request" }).click();
  await expect(agentPage.getByRole("button", { name: "Start work" })).toBeVisible();
  await agentPage.getByRole("button", { name: "Start work" }).click();

  await agentPage.getByLabel("Message visibility").selectOption("internal");
  await agentPage.locator("#agent-message").fill(privateNote);
  await agentPage.getByRole("button", { name: "Add private note" }).click();
  await expect(agentPage.getByText(privateNote)).toBeVisible();
  await agentPage.getByLabel("Message visibility").selectOption("public");
  await agentPage.locator("#agent-message").fill(publicReply);
  await agentPage.getByRole("button", { name: "Send public reply" }).click();
  await expect(agentPage.getByText(publicReply)).toBeVisible();
  await agentPage.getByRole("button", { name: "Wait for customer" }).click();
  await expect(agentPage.getByRole("status")).toContainText("Waiting for customer");

  await customerPage.goto(customerTicketUrl);
  await expect(customerPage.getByText("Waiting for you")).toBeVisible();
  await expect(customerPage.getByText(publicReply)).toBeVisible();
  await expect(customerPage.getByText(privateNote)).toHaveCount(0);
  const customerReply = `Customer QA response ${reference}: the update answers my question.`;
  await customerPage.getByLabel("Add a reply").fill(customerReply);
  await customerPage.getByRole("button", { name: "Send reply" }).click();
  await expect(customerPage.getByText(customerReply)).toBeVisible();
  await expect(customerPage.getByText("In progress")).toBeVisible();

  await agentPage.reload();
  await expect(agentPage.getByRole("heading", { name: subject })).toBeVisible();
  await agentPage.getByRole("button", { name: "Resolve request" }).click();
  await agentPage.getByLabel("Public resolution summary").fill(
    "We confirmed the sample support workflow and shared the resolution with the customer.",
  );
  await agentPage.getByRole("button", { name: "Resolve", exact: true }).click();
  await expect(agentPage.getByText("Request resolved.")).toBeVisible();

  await customerPage.reload();
  await expect(customerPage.getByText("Resolved", { exact: true })).toBeVisible();
  await customerPage.getByRole("button", { name: "Reopen request" }).click();
  await customerPage.getByLabel("What still needs attention?").fill(
    "The synthetic request needs one more step after reviewing the resolution.",
  );
  await customerPage.getByRole("button", { name: "Send and reopen" }).click();
  await expect(customerPage.getByText("Open", { exact: true })).toBeVisible();

  await agentContext.close();
  await customerContext.close();
});
