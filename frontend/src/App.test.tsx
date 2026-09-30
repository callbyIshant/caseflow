import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

describe("CaseFlow landing page", () => {
  let signedInRole: "customer" | "agent" = "customer";
  let ticketClaimed = false;
  let unauthorizedSummary = false;
  const staffTicketId = "ticket-42";

  beforeEach(() => {
    signedInRole = "customer";
    ticketClaimed = false;
    unauthorizedSummary = false;
    window.history.replaceState({}, "", "/");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input);
        if (path.endsWith("/auth/session")) {
          return new Response(JSON.stringify({ authenticated: false }), { status: 200 });
        }
        if (path.endsWith("/auth/register")) {
          const request = JSON.parse(String(init?.body)) as { full_name: string; email: string };
          return new Response(JSON.stringify({
            csrf_token: "test-csrf-token",
            user: {
              id: "user-1",
              full_name: request.full_name,
              email: request.email,
              role: "customer",
              created_at: "2026-09-30T00:00:00Z",
            },
          }), { status: 201 });
        }
        if (path.endsWith("/auth/login")) {
          return new Response(JSON.stringify({
            csrf_token: "test-csrf-token",
            user: {
              id: "staff-1",
              full_name: "Alex Agent",
              email: "agent@example.com",
              role: signedInRole,
              created_at: "2026-09-30T00:00:00Z",
            },
          }), { status: 200 });
        }
        if (path.endsWith("/tickets/summary")) {
          if (unauthorizedSummary) {
            return new Response(JSON.stringify({ error: { code: "AUTH_REQUIRED", message: "Sign in to continue." } }), { status: 401 });
          }
          return new Response(JSON.stringify({
            ticket_counts: { open: 0, in_progress: 0, waiting_customer: 0, resolved: 0, closed: 0 },
            recent_tickets: [],
            total_tickets: 0,
          }), { status: 200 });
        }
        if (path.endsWith(`/tickets/${staffTicketId}/claim`)) {
          ticketClaimed = true;
          return new Response(JSON.stringify({
            id: staffTicketId,
            reference: "CF-000042",
            subject: "Example synthetic issue",
            description: "A customer describes an example support issue for the queue UI test.",
            category: "technical",
            priority: "medium",
            status: "open",
            created_at: "2026-09-30T00:00:00Z",
            updated_at: "2026-09-30T00:00:00Z",
            resolved_at: null,
            closed_at: null,
            version: 2,
            customer_id: "customer-1",
            customer_name: "Jordan Customer",
            assignee_id: "staff-1",
            assignee_name: "Alex Agent",
          }), { status: 200 });
        }
        if (path.endsWith(`/tickets/${staffTicketId}/timeline`)) {
          return new Response(JSON.stringify({
            ticket_id: staffTicketId,
            items: [{
              id: "event-1",
              kind: "event",
              created_at: "2026-09-30T00:00:00Z",
              actor_name: "Jordan Customer",
              visibility: "public",
              summary: "Request submitted",
              event_type: "ticket_created",
              old_value: null,
              new_value: { reference: "CF-000042" },
            }],
          }), { status: 200 });
        }
        if (path.endsWith(`/tickets/${staffTicketId}`)) {
          return new Response(JSON.stringify({
            id: staffTicketId,
            reference: "CF-000042",
            subject: "Example synthetic issue",
            description: "A customer describes an example support issue for the queue UI test.",
            category: "technical",
            priority: "medium",
            status: "open",
            created_at: "2026-09-30T00:00:00Z",
            updated_at: "2026-09-30T00:00:00Z",
            resolved_at: null,
            closed_at: null,
            version: ticketClaimed ? 2 : 1,
            customer_id: "customer-1",
            customer_name: "Jordan Customer",
            assignee_id: ticketClaimed ? "staff-1" : null,
            assignee_name: ticketClaimed ? "Alex Agent" : null,
          }), { status: 200 });
        }
        if (path.includes("/tickets?" ) || path.endsWith("/tickets")) {
          return new Response(JSON.stringify({
            items: [{
              id: staffTicketId,
              reference: "CF-000042",
              subject: "Example synthetic issue",
              category: "technical",
              priority: "medium",
              status: "open",
              created_at: "2026-09-30T00:00:00Z",
              updated_at: "2026-09-30T00:00:00Z",
              customer_id: "customer-1",
              customer_name: "Jordan Customer",
              assignee_id: ticketClaimed ? "staff-1" : null,
              assignee_name: ticketClaimed ? "Alex Agent" : null,
            }],
            pagination: { page: 1, page_size: 20, total_items: 1, total_pages: 1 },
          }), { status: 200 });
        }
        if (path.endsWith("/auth/logout")) return new Response(null, { status: 204 });
        return new Response(JSON.stringify({ error: { message: "Unexpected request" } }), { status: 500 });
      }),
    );
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("explains the product and portfolio-demo boundary", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Good support starts with a clearer picture." })).toBeInTheDocument();
    expect(screen.getByText(/portfolio project with fictional, synthetic data/i)).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Main navigation" })).toBeInTheDocument();
  });

  it("shows the fixed read-only tour without requesting live ticket data", async () => {
    window.history.replaceState({}, "", "/demo");
    render(<App />);

    expect(await screen.findByRole("heading", { name: "A clearer view of every request." })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /CF-000/ })).toHaveLength(3);
    expect(screen.getByText(/Nothing here connects to the live ticket system/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /CF-000179/ }));
    expect(screen.getByRole("heading", { name: "Where can I find last month’s statement?" })).toBeInTheDocument();
    expect(screen.getByText(/This preview is read-only/i)).toBeInTheDocument();
    expect(document.title).toBe("Product tour | CaseFlow");
    expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).includes("/tickets"))).toBe(false);
  });

  it("renders a styled 404 for unknown client routes", async () => {
    window.history.replaceState({}, "", "/this-page-is-not-part-of-caseflow");
    render(<App />);

    expect(await screen.findByRole("heading", { name: "We can’t find that page." })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to home" })).toHaveAttribute("href", "/");
    expect(document.title).toBe("Page not found | CaseFlow");
  });

  it("clears stale authentication and redirects to sign-in after an API 401", async () => {
    unauthorizedSummary = true;
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Good support starts with a clearer picture." })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: "Create account" }));
    expect(await screen.findByRole("heading", { name: "Create your account" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Jordan Example" } });
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "jordan@example.com" } });
    fireEvent.change(screen.getByLabelText(/Password/), { target: { value: "patient example passphrase" } });
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "patient example passphrase" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/login");
    expect(new URLSearchParams(window.location.search).get("next")).toBe("/app/dashboard");
  });

  it("registers a customer, opens their dashboard and signs them out", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("link", { name: "Create account" }));
    expect(await screen.findByRole("heading", { name: "Create your account" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Jordan Example" } });
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "jordan@example.com" } });
    fireEvent.change(screen.getByLabelText(/Password/), { target: { value: "patient example passphrase" } });
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "patient example passphrase" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("heading", { name: "Your overview" })).toBeInTheDocument();
    expect(await screen.findByText("No requests yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Create your first request/ })).toHaveAttribute("href", "/app/tickets/new");
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(await screen.findByRole("heading", { name: "Good support starts with a clearer picture." })).toBeInTheDocument();
    await waitFor(() => {
      const postCall = vi.mocked(fetch).mock.calls.find(([input]) => String(input).endsWith("/auth/register"));
      expect(postCall?.[1]?.credentials).toBe("same-origin");
      const logoutCall = vi.mocked(fetch).mock.calls.find(([input]) => String(input).endsWith("/auth/logout"));
      expect(new Headers(logoutCall?.[1]?.headers).get("X-CSRF-Token")).toBe("test-csrf-token");
    });
  });

  it("routes support staff to the shared queue and lets an agent claim a request", async () => {
    signedInRole = "agent";
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Good support starts with a clearer picture." })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: "Sign in" }));
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "agent@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "test-only-agent-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("heading", { name: "Shared queue" })).toBeInTheDocument();
    expect(await screen.findByText("Example synthetic issue")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: /Example synthetic issue/ }));
    expect(await screen.findByRole("button", { name: "Claim request" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Claim request" }));
    expect(await screen.findByText("Request claimed by you.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start work" })).toBeInTheDocument();
  });
});
