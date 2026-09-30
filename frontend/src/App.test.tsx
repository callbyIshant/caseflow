import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

describe("CaseFlow landing page", () => {
  beforeEach(() => {
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

  it("registers a customer and opens a protected customer workspace", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("link", { name: "Create account" }));
    expect(await screen.findByRole("heading", { name: "Create your account" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Jordan Example" } });
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "jordan@example.com" } });
    fireEvent.change(screen.getByLabelText(/Password/), { target: { value: "patient example passphrase" } });
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "patient example passphrase" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("heading", { name: "Customer workspace" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(await screen.findByRole("heading", { name: "Good support starts with a clearer picture." })).toBeInTheDocument();
    await waitFor(() => {
      const postCall = vi.mocked(fetch).mock.calls.find(([input]) => String(input).endsWith("/auth/register"));
      expect(postCall?.[1]?.credentials).toBe("same-origin");
      const logoutCall = vi.mocked(fetch).mock.calls.find(([input]) => String(input).endsWith("/auth/logout"));
      expect(new Headers(logoutCall?.[1]?.headers).get("X-CSRF-Token")).toBe("test-csrf-token");
    });
  });
});
