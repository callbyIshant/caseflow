import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, NavLink, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ApiError } from "../api/client";
import {
  claimSupportTicket,
  getSupportAgents,
  getSupportTicket,
  getSupportTickets,
  getSupportTimeline,
  reopenSupportTicket,
  sendStaffMessage,
  setTicketAssignee,
  setTicketPriority,
  setTicketStatus,
  supportCategoryLabel,
  supportStatusLabel,
  type SupportAgent,
  type SupportTicketDetail as TicketDetail,
  type SupportTimelineItem,
} from "../api/support";
import type { TicketPriority, TicketStatus } from "../api/tickets";
import { useAuth } from "../auth/AuthContext";

const priorities: TicketPriority[] = ["low", "medium", "high"];
const statuses: TicketStatus[] = ["open", "in_progress", "waiting_customer", "resolved", "closed"];

function displayDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function ErrorNotice({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="ticket-error" role="alert"><p>{message}</p>{onRetry && <button className="text-button" type="button" onClick={onRetry}>Try again</button>}</div>;
}

function AgentShell({ children, hasUnsavedDraft = false }: { children: ReactNode; hasUnsavedDraft?: boolean }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [signOutError, setSignOutError] = useState("");
  async function signOut() {
    setSignOutError("");
    if (hasUnsavedDraft && !window.confirm("You have an unsent update. Sign out and discard it?")) return;
    try {
      await logout();
      navigate("/", { replace: true });
    } catch {
      setSignOutError("We could not sign you out. Please try again.");
    }
  }
  return <main className="agent-app">
    <header className="agent-topbar">
      <Link className="brand" to="/agent/queue" aria-label="CaseFlow support queue"><span className="brand-mark-small">C</span><span>caseflow</span><span className="agent-brand-tag">SUPPORT DESK</span></Link>
      <div className="customer-account"><span className="customer-greeting">{user?.full_name}{user?.role === "admin" ? " · Admin" : " · Agent"}</span><button className="text-button" type="button" onClick={signOut}>Sign out</button></div>
    </header>
    <div className="agent-body">
      <aside className="agent-sidebar" aria-label="Support workspace">
        <p className="sidebar-eyebrow">TEAM WORKSPACE</p>
        <nav className="workspace-nav" aria-label="Support navigation"><NavLink to="/agent/queue" className={({ isActive }) => isActive ? "workspace-link active" : "workspace-link"}>Shared queue</NavLink></nav>
        <p className="agent-sidebar-note">Every request stays with its history and next step.</p>
      </aside>
      <section className="agent-main" aria-label="Support workspace content">
        {signOutError && <ErrorNotice message={signOutError} />}
        {children}
      </section>
    </div>
  </main>;
}

export function AgentQueue() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [queryDraft, setQueryDraft] = useState(searchParams.get("q") ?? "");
  const [refreshCount, setRefreshCount] = useState(0);
  const [data, setData] = useState<Awaited<ReturnType<typeof getSupportTickets>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const page = Number(searchParams.get("page") ?? "1");
  const filterKey = searchParams.toString();

  useEffect(() => {
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError("");
    void getSupportTickets(new URLSearchParams(filterKey)).then((result) => {
      if (!cancelled) setData(result);
    }).catch((cause: unknown) => {
      if (!cancelled) setError(cause instanceof ApiError ? cause.message : "We could not load the support queue.");
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [filterKey, refreshCount]);

  useEffect(() => {
    // URL changes (back/forward) are the source of truth for this search box.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setQueryDraft(searchParams.get("q") ?? "");
  }, [searchParams]);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = new URLSearchParams(searchParams);
    const query = queryDraft.trim();
    if (query) next.set("q", query); else next.delete("q");
    next.delete("page");
    setSearchParams(next);
  }

  function updateFilter(key: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value); else next.delete(key);
    next.delete("page");
    setSearchParams(next);
  }

  function updatePage(nextPage: number) {
    const next = new URLSearchParams(searchParams);
    next.set("page", String(nextPage));
    setSearchParams(next);
  }

  const admin = user?.role === "admin";
  return <AgentShell>
    <div className="page-heading"><div><span className="auth-kicker">NORTHSTAR SERVICES · SUPPORT DESK</span><h1>Shared queue</h1><p>Find the next request that needs a clear owner and a thoughtful response.</p></div><button className="filter-button queue-refresh" type="button" onClick={() => setRefreshCount((count) => count + 1)}>Refresh queue</button></div>
    <form className="filter-panel agent-filter-panel" aria-label="Filter support queue" onSubmit={applyFilters}>
      <label className="ticket-search" htmlFor="agent-search">Search requests<div><input id="agent-search" type="search" minLength={2} maxLength={100} value={queryDraft} onChange={(event) => setQueryDraft(event.target.value)} placeholder="Subject or reference" /><button className="filter-button" type="submit">Search</button></div></label>
      <label className="filter-field">Status<select value={searchParams.get("status") ?? ""} onChange={(event) => updateFilter("status", event.target.value)}><option value="">All statuses</option>{statuses.map((status) => <option key={status} value={status}>{supportStatusLabel[status]}</option>)}</select></label>
      <label className="filter-field">Category<select value={searchParams.get("category") ?? ""} onChange={(event) => updateFilter("category", event.target.value)}><option value="">All categories</option>{Object.entries(supportCategoryLabel).map(([category, label]) => <option key={category} value={category}>{label}</option>)}</select></label>
      <label className="filter-field">Priority<select value={searchParams.get("priority") ?? ""} onChange={(event) => updateFilter("priority", event.target.value)}><option value="">All priorities</option>{priorities.map((priority) => <option key={priority} value={priority}>{priority[0]?.toUpperCase()}{priority.slice(1)}</option>)}</select></label>
      <label className="filter-field">Assignment<select value={searchParams.get("assigned_to") ?? ""} onChange={(event) => updateFilter("assigned_to", event.target.value)}><option value="">Everyone</option><option value="me">{admin ? "Assigned to me" : "Assigned to me"}</option><option value="unassigned">Unassigned</option></select></label>
    </form>
    {loading && <div className="ticket-loading" role="status">Loading the shared queue…</div>}
    {error && <ErrorNotice message={error} onRetry={() => setRefreshCount((count) => count + 1)} />}
    {!loading && !error && data && <>
      <p className="results-count" aria-live="polite">{data.pagination.total_items} {data.pagination.total_items === 1 ? "request" : "requests"}</p>
      {data.items.length === 0 ? <div className="empty-state agent-empty"><span className="empty-symbol" aria-hidden="true">✓</span><h2>Queue is clear</h2><p>No requests match these filters. New customer requests will appear here.</p></div> : <div className="agent-queue-table" role="table" aria-label="Support request queue">
        <div className="agent-queue-head" role="row"><span role="columnheader">Request</span><span role="columnheader">Customer</span><span role="columnheader">Status</span><span role="columnheader">Priority</span><span role="columnheader">Assigned to</span><span role="columnheader">Updated</span></div>
        {data.items.map((ticket) => <div className="agent-queue-row" role="row" key={ticket.id}>
          <span className="agent-request-title" role="cell"><Link className="agent-request-link" to={`/agent/tickets/${ticket.id}`}><span className="ticket-ref">{ticket.reference}</span><strong>{ticket.subject}</strong><small>{supportCategoryLabel[ticket.category]}</small></Link></span>
          <span className="agent-customer-name" role="cell">{ticket.customer_name}</span>
          <span role="cell"><StatusBadge status={ticket.status} /></span>
          <span className={`agent-priority priority-${ticket.priority}`} role="cell">{ticket.priority.charAt(0).toUpperCase() + ticket.priority.slice(1)}</span>
          <span className={ticket.assignee_name ? "agent-assignee" : "agent-unassigned"} role="cell">{ticket.assignee_name ?? "Unassigned"}</span>
          <time className="ticket-row-date" dateTime={ticket.updated_at} role="cell">{displayDate(ticket.updated_at)}</time>
        </div>)}
      </div>}
      {data.pagination.total_pages > 1 && <nav className="pagination-nav" aria-label="Queue pages"><button className="filter-button" type="button" disabled={page <= 1} onClick={() => updatePage(page - 1)}>Previous</button><span>Page {page} of {data.pagination.total_pages}</span><button className="filter-button" type="button" disabled={page >= data.pagination.total_pages} onClick={() => updatePage(page + 1)}>Next</button></nav>}
    </>}
  </AgentShell>;
}

function StatusBadge({ status }: { status: TicketStatus }) {
  return <span className={`status-badge status-${status.replaceAll("_", "-")}`}>{supportStatusLabel[status]}</span>;
}

export function AgentTicketDetail() {
  const { ticketId = "" } = useParams();
  const { user } = useAuth();
  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [timeline, setTimeline] = useState<SupportTimelineItem[]>([]);
  const [staff, setStaff] = useState<SupportAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const [priorityDraft, setPriorityDraft] = useState<TicketPriority>("medium");
  const [assigneeDraft, setAssigneeDraft] = useState("");
  const [visibility, setVisibility] = useState<"public" | "internal">("public");
  const [message, setMessage] = useState("");
  const [showResolution, setShowResolution] = useState(false);
  const [resolutionMessage, setResolutionMessage] = useState("");
  const [showReopen, setShowReopen] = useState(false);
  const [reopenReason, setReopenReason] = useState("");
  const isAdmin = user?.role === "admin";
  const isAssignedAgent = user?.role === "agent" && ticket?.assignee_id === user.id;
  const canWrite = isAdmin || isAssignedAgent;
  const canMessage = canWrite && ticket !== null && !["resolved", "closed"].includes(ticket.status);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [ticketResult, timelineResult, staffResult] = await Promise.all([
        getSupportTicket(ticketId),
        getSupportTimeline(ticketId),
        isAdmin ? getSupportAgents() : Promise.resolve([]),
      ]);
      setTicket(ticketResult);
      setTimeline(timelineResult.items);
      setPriorityDraft(ticketResult.priority);
      setAssigneeDraft(ticketResult.assignee_id ?? "");
      setStaff(staffResult);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "We could not load this request.");
    } finally {
      setLoading(false);
    }
  }, [ticketId, isAdmin]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  async function act(action: () => Promise<unknown>, successMessage: string) {
    setBusy(true);
    setActionError("");
    setSuccess("");
    try {
      await action();
      await load();
      setSuccess(successMessage);
      setMessage("");
      setResolutionMessage("");
      setReopenReason("");
      setShowResolution(false);
      setShowReopen(false);
    } catch (cause) {
      const messageText = cause instanceof ApiError
        ? cause.status === 409 ? `${cause.message} The request may have changed; refresh the latest details before trying again.` : cause.message
        : "We could not save that update. Please try again.";
      setActionError(messageText);
    } finally {
      setBusy(false);
    }
  }

  function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!message.trim()) return;
    void act(() => sendStaffMessage(ticketId, message, visibility), visibility === "internal" ? "Private note added." : "Public reply sent.");
  }

  function submitResolution(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void act(() => setTicketStatus(ticketId, "resolved", resolutionMessage), "Request resolved.");
  }

  function submitReopen(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void act(() => reopenSupportTicket(ticketId, reopenReason), "Request reopened.");
  }

  function closeResolvedRequest() {
    const hasUnsentUpdate = Boolean(message.trim() || resolutionMessage.trim());
    const confirmation = hasUnsentUpdate
      ? "This request will be closed and your unsent update will be discarded. Continue?"
      : "Close this resolved request? The customer will no longer be able to reply.";
    if (window.confirm(confirmation)) {
      void act(() => setTicketStatus(ticketId, "closed"), "Request closed.");
    }
  }

  return <AgentShell hasUnsavedDraft={Boolean(message.trim() || resolutionMessage.trim() || reopenReason.trim())}>
    <div className="detail-back"><Link to="/agent/queue">← Shared queue</Link></div>
    {loading && <div className="ticket-loading" role="status">Loading this request…</div>}
    {error && <ErrorNotice message={error} onRetry={() => void load()} />}
    {ticket && !error && <>
      <div className="ticket-detail-heading agent-detail-heading"><div><span className="ticket-ref">{ticket.reference} · {supportCategoryLabel[ticket.category]}</span><h1>{ticket.subject}</h1><p>Submitted by {ticket.customer_name} · {displayDate(ticket.created_at)}</p></div><StatusBadge status={ticket.status} /></div>
      {actionError && <div className="agent-feedback"><ErrorNotice message={actionError} onRetry={() => void load()} /></div>}
      {success && <p className="agent-success" role="status">{success}</p>}
      <section className="ticket-detail-grid agent-ticket-grid">
        <div className="ticket-detail-primary">
          <article className="ticket-description-card"><div className="section-label">CUSTOMER REQUEST</div><p>{ticket.description}</p></article>
          {(canWrite || (ticket.status === "open" && ticket.assignee_id === null)) && ticket.status !== "closed" && <section className="agent-actions-card" aria-label="Request actions">
            <div className="section-label">NEXT STEP</div>
            <div className="agent-action-buttons">
              {ticket.status === "open" && ticket.assignee_id === null && <button className="button button-primary" type="button" disabled={busy} onClick={() => void act(() => claimSupportTicket(ticketId), "Request claimed by you.")}>Claim request</button>}
              {ticket.status === "open" && ticket.assignee_id !== null && <button className="button button-primary" type="button" disabled={busy} onClick={() => void act(() => setTicketStatus(ticketId, "in_progress"), "Work started.")}>Start work</button>}
              {ticket.status === "in_progress" && <button className="filter-button" type="button" disabled={busy} onClick={() => void act(() => setTicketStatus(ticketId, "waiting_customer"), "Waiting for customer.")}>Wait for customer</button>}
              {ticket.status === "waiting_customer" && <button className="button button-primary" type="button" disabled={busy} onClick={() => void act(() => setTicketStatus(ticketId, "in_progress"), "Work resumed.")}>Resume work</button>}
              {["in_progress", "waiting_customer"].includes(ticket.status) && <button className="button button-primary" type="button" disabled={busy} onClick={() => setShowResolution((value) => !value)}>Resolve request</button>}
              {ticket.status === "resolved" && <><button className="filter-button" type="button" disabled={busy} onClick={closeResolvedRequest}>Close request</button><button className="filter-button" type="button" disabled={busy} onClick={() => setShowReopen((value) => !value)}>Reopen request</button></>}
            </div>
            {ticket.status === "open" && ticket.assignee_id !== null && !isAdmin && !isAssignedAgent && <p className="agent-readonly-note">This request is assigned to {ticket.assignee_name}. You can review the history while an administrator manages reassignment.</p>}
            {isAdmin && <div className="agent-admin-controls">
              <label htmlFor="request-assignee">Assigned support member</label>
              <div><select id="request-assignee" value={assigneeDraft} disabled={busy || ["resolved", "closed"].includes(ticket.status)} onChange={(event) => setAssigneeDraft(event.target.value)}><option value="">Unassigned</option>{staff.map((member) => <option key={member.id} value={member.id}>{member.full_name}{member.role === "admin" ? " · Admin" : ""}</option>)}</select><button className="filter-button" type="button" disabled={busy || assigneeDraft === (ticket.assignee_id ?? "") || ["resolved", "closed"].includes(ticket.status)} onClick={() => void act(() => setTicketAssignee(ticketId, assigneeDraft || null), "Assignment updated.")}>Save assignment</button></div>
            </div>}
            {canWrite && !["resolved", "closed"].includes(ticket.status) && <div className="agent-admin-controls agent-priority-control"><label htmlFor="request-priority">Priority</label><div><select id="request-priority" value={priorityDraft} disabled={busy} onChange={(event) => setPriorityDraft(event.target.value as TicketPriority)}>{priorities.map((priority) => <option value={priority} key={priority}>{priority[0]?.toUpperCase()}{priority.slice(1)}</option>)}</select><button className="filter-button" type="button" disabled={busy || priorityDraft === ticket.priority} onClick={() => void act(() => setTicketPriority(ticketId, priorityDraft), "Priority updated.")}>Save priority</button></div></div>}
            {showResolution && <form className="agent-inline-form" onSubmit={submitResolution}><label htmlFor="resolution-summary">Public resolution summary<textarea id="resolution-summary" required minLength={10} maxLength={1000} rows={3} value={resolutionMessage} onChange={(event) => setResolutionMessage(event.target.value)} placeholder="Summarize the resolution for the customer" /></label><div className="reply-footer"><small>{resolutionMessage.length}/1000 · Shared with the customer</small><button className="button button-primary" type="submit" disabled={busy || resolutionMessage.trim().length < 10}>{busy ? "Saving…" : "Resolve"}</button></div></form>}
            {showReopen && <form className="agent-inline-form" onSubmit={submitReopen}><label htmlFor="reopen-reason">Why is this request reopening?<textarea id="reopen-reason" required minLength={10} maxLength={3000} rows={3} value={reopenReason} onChange={(event) => setReopenReason(event.target.value)} placeholder="Give the customer a clear explanation" /></label><div className="reply-footer"><small>{reopenReason.length}/3000 · Shared with the customer</small><button className="button button-primary" type="submit" disabled={busy || reopenReason.trim().length < 10}>{busy ? "Saving…" : "Reopen"}</button></div></form>}
          </section>}
          {!canWrite && ticket.status !== "closed" && !(ticket.status === "open" && ticket.assignee_id === null) && <div className="agent-readonly-banner">This request belongs to {ticket.assignee_name ?? "the shared queue"}. You can review its history; updates are limited to its assigned agent and administrators.</div>}
          {ticket.status === "closed" && <div className="closed-notice">This request is closed and read-only.</div>}
          <section className="timeline-card agent-timeline" aria-labelledby="agent-timeline-title"><div className="section-label" id="agent-timeline-title">FULL ACTIVITY HISTORY</div>{timeline.length === 0 ? <p className="timeline-empty">There is no activity yet.</p> : <ol className="timeline-list">{timeline.map((item) => <AgentTimelineEntry key={item.id} item={item} />)}</ol>}</section>
          {canMessage && <form className="reply-card agent-message-card" onSubmit={submitMessage}><div className="section-label">MESSAGE THE CUSTOMER OR LEAVE A PRIVATE NOTE</div><label htmlFor="message-visibility">Message visibility<select id="message-visibility" value={visibility} disabled={busy} onChange={(event) => setVisibility(event.target.value as "public" | "internal")}><option value="public">Public reply · visible to customer</option><option value="internal">Private note · support team only</option></select></label><label htmlFor="agent-message">{visibility === "public" ? "Public reply" : "Private note"}<textarea id="agent-message" required minLength={1} maxLength={3000} rows={4} value={message} onChange={(event) => setMessage(event.target.value)} placeholder={visibility === "public" ? "Write a helpful update for the customer" : "Add context for the support team"} /></label><div className="reply-footer"><small>{message.length}/3000 · {visibility === "public" ? "The customer will see this reply" : "Only support staff can see this note"}</small><button className="button button-primary" type="submit" disabled={busy || !message.trim()}>{busy ? "Sending…" : visibility === "public" ? "Send public reply" : "Add private note"}</button></div></form>}
        </div>
        <aside className="ticket-detail-aside"><div className="section-label">REQUEST DETAILS</div><dl><dt>Reference</dt><dd>{ticket.reference}</dd><dt>Customer</dt><dd>{ticket.customer_name}</dd><dt>Category</dt><dd>{supportCategoryLabel[ticket.category]}</dd><dt>Priority</dt><dd className="priority-value">{ticket.priority.charAt(0).toUpperCase() + ticket.priority.slice(1)}</dd><dt>Assigned to</dt><dd>{ticket.assignee_name ?? "Unassigned"}</dd><dt>Created</dt><dd>{displayDate(ticket.created_at)}</dd><dt>Last updated</dt><dd>{displayDate(ticket.updated_at)}</dd>{ticket.resolved_at && <><dt>Resolved</dt><dd>{displayDate(ticket.resolved_at)}</dd></>}</dl><div className="aside-note">Internal notes and assignment events are available only in the support workspace.</div></aside>
      </section>
    </>}
  </AgentShell>;
}

function AgentTimelineEntry({ item }: { item: SupportTimelineItem }) {
  const event = item.kind === "event";
  const internal = item.visibility === "internal";
  return <li className={`timeline-entry ${event ? "timeline-event" : "timeline-message"} ${internal ? "timeline-internal" : ""}`}>
    <span className="timeline-marker" aria-hidden="true">{internal ? "•" : item.actor_name.slice(0, 1).toUpperCase()}</span>
    <div className="timeline-entry-content"><div className="timeline-entry-meta"><strong>{event ? item.summary : item.actor_name}{internal && <span className="internal-label"> · INTERNAL</span>}</strong><time dateTime={item.created_at}>{displayDate(item.created_at)}</time></div>{item.body && <p>{item.body}</p>}{event && item.new_value && <small className="event-change">{formatEventValues(item.old_value, item.new_value)}</small>}</div>
  </li>;
}

function formatEventValues(oldValue: Record<string, unknown> | null | undefined, newValue: Record<string, unknown>): string {
  const oldStatus = oldValue?.status;
  const nextStatus = newValue.status;
  if (typeof oldStatus === "string" && typeof nextStatus === "string") {
    return `${supportStatusLabel[oldStatus as TicketStatus] ?? oldStatus} → ${supportStatusLabel[nextStatus as TicketStatus] ?? nextStatus}`;
  }
  const oldPriority = oldValue?.priority;
  const nextPriority = newValue.priority;
  if (typeof oldPriority === "string" && typeof nextPriority === "string") return `${oldPriority} → ${nextPriority}`;
  return "";
}
