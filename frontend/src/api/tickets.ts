import { apiRequest } from "./client";

export type TicketStatus = "open" | "in_progress" | "waiting_customer" | "resolved" | "closed";
export type TicketCategory = "account" | "billing" | "technical" | "general";
export type TicketPriority = "low" | "medium" | "high";

export type TicketSummary = {
  id: string;
  reference: string;
  subject: string;
  category: TicketCategory;
  priority: TicketPriority;
  status: TicketStatus;
  created_at: string;
  updated_at: string;
};

export type TicketDetail = TicketSummary & {
  description: string;
  resolved_at: string | null;
  closed_at: string | null;
};

export type Pagination = {
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
};

export type TicketPage = { items: TicketSummary[]; pagination: Pagination };
export type TicketCounts = Record<TicketStatus, number>;
export type DashboardSummary = {
  ticket_counts: TicketCounts;
  recent_tickets: TicketSummary[];
  total_tickets: number;
};

export type TimelineItem = {
  kind: "message" | "event";
  id: string;
  created_at: string;
  actor_name: string;
  visibility: "public";
  body?: string | null;
  summary?: string | null;
};
export type TicketTimeline = { ticket_id: string; items: TimelineItem[] };

export function getDashboardSummary(): Promise<DashboardSummary> {
  return apiRequest("/tickets/summary");
}

export function getTickets(params: URLSearchParams): Promise<TicketPage> {
  const query = params.toString();
  return apiRequest(`/tickets${query ? `?${query}` : ""}`);
}

export function getTicket(ticketId: string): Promise<TicketDetail> {
  return apiRequest(`/tickets/${encodeURIComponent(ticketId)}`);
}

export function getTicketTimeline(ticketId: string): Promise<TicketTimeline> {
  return apiRequest(`/tickets/${encodeURIComponent(ticketId)}/timeline`);
}

export function createTicket(payload: {
  subject: string;
  description: string;
  category: TicketCategory;
}): Promise<TicketDetail> {
  return apiRequest("/tickets", { method: "POST", body: JSON.stringify(payload) });
}

export function addTicketReply(ticketId: string, body: string): Promise<TimelineItem> {
  return apiRequest(`/tickets/${encodeURIComponent(ticketId)}/messages`, {
    method: "POST",
    body: JSON.stringify({ body, visibility: "public" }),
  });
}

export function reopenCustomerTicket(ticketId: string, reason: string): Promise<TicketDetail> {
  return apiRequest(`/tickets/${encodeURIComponent(ticketId)}/reopen`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}
