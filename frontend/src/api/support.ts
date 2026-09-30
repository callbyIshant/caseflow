import { apiRequest } from "./client";
import type {
  Pagination,
  TicketCategory,
  TicketDetail,
  TicketPriority,
  TicketStatus,
  TicketSummary,
} from "./tickets";

export type SupportTicketSummary = TicketSummary & {
  customer_id: string;
  customer_name: string;
  assignee_id: string | null;
  assignee_name: string | null;
};

export type SupportTicketDetail = SupportTicketSummary & TicketDetail & {
  version: number;
};

export type SupportTicketPage = { items: SupportTicketSummary[]; pagination: Pagination };
export type SupportTimelineItem = {
  kind: "message" | "event";
  id: string;
  created_at: string;
  actor_name: string;
  visibility: "public" | "internal";
  body?: string | null;
  summary?: string | null;
  event_type?: string | null;
  old_value?: Record<string, unknown> | null;
  new_value?: Record<string, unknown> | null;
};
export type SupportTicketTimeline = { ticket_id: string; items: SupportTimelineItem[] };
export type SupportAgent = { id: string; full_name: string; role: "agent" | "admin" };

export function getSupportTickets(params: URLSearchParams): Promise<SupportTicketPage> {
  const query = params.toString();
  return apiRequest(`/tickets${query ? `?${query}` : ""}`);
}

export function getSupportTicket(ticketId: string): Promise<SupportTicketDetail> {
  return apiRequest(`/tickets/${encodeURIComponent(ticketId)}`);
}

export function getSupportTimeline(ticketId: string): Promise<SupportTicketTimeline> {
  return apiRequest(`/tickets/${encodeURIComponent(ticketId)}/timeline`);
}

export function getSupportAgents(): Promise<SupportAgent[]> {
  return apiRequest("/support/agents");
}

export function claimSupportTicket(ticketId: string): Promise<SupportTicketDetail> {
  return apiRequest(`/tickets/${encodeURIComponent(ticketId)}/claim`, { method: "POST" });
}

export function setTicketAssignee(ticketId: string, assigneeId: string | null): Promise<SupportTicketDetail> {
  return apiRequest(`/tickets/${encodeURIComponent(ticketId)}/assignee`, {
    method: "PUT",
    body: JSON.stringify({ assignee_id: assigneeId }),
  });
}

export function setTicketPriority(ticketId: string, priority: TicketPriority): Promise<SupportTicketDetail> {
  return apiRequest(`/tickets/${encodeURIComponent(ticketId)}/priority`, {
    method: "PATCH",
    body: JSON.stringify({ priority }),
  });
}

export function setTicketStatus(
  ticketId: string,
  status: TicketStatus,
  resolutionMessage?: string,
): Promise<SupportTicketDetail> {
  return apiRequest(`/tickets/${encodeURIComponent(ticketId)}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status, ...(resolutionMessage ? { resolution_message: resolutionMessage } : {}) }),
  });
}

export function reopenSupportTicket(ticketId: string, reason: string): Promise<SupportTicketDetail> {
  return apiRequest(`/tickets/${encodeURIComponent(ticketId)}/reopen`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export function sendStaffMessage(
  ticketId: string,
  body: string,
  visibility: "public" | "internal",
): Promise<SupportTimelineItem> {
  return apiRequest(`/tickets/${encodeURIComponent(ticketId)}/messages`, {
    method: "POST",
    body: JSON.stringify({ body, visibility }),
  });
}

export const supportCategoryLabel: Record<TicketCategory, string> = {
  account: "Account access",
  billing: "Billing",
  technical: "Technical help",
  general: "Something else",
};

export const supportStatusLabel: Record<TicketStatus, string> = {
  open: "Open",
  in_progress: "In progress",
  waiting_customer: "Waiting for customer",
  resolved: "Resolved",
  closed: "Closed",
};
