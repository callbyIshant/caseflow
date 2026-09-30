import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, NavLink, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ApiError } from "../api/client";
import {
  addTicketReply,
  createTicket,
  getDashboardSummary,
  getTicket,
  getTicketTimeline,
  getTickets,
  reopenCustomerTicket,
  type DashboardSummary,
  type TicketCategory,
  type TicketDetail,
  type TicketPage,
  type TicketStatus,
  type TicketSummary,
  type TimelineItem,
} from "../api/tickets";
import { useAuth } from "../auth/AuthContext";

const statusLabels: Record<TicketStatus, string> = {
  open: "Open",
  in_progress: "In progress",
  waiting_customer: "Waiting for you",
  resolved: "Resolved",
  closed: "Closed",
};

const categoryLabels: Record<TicketCategory, string> = {
  account: "Account access",
  billing: "Billing",
  technical: "Technical help",
  general: "Something else",
};

function displayDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function StatusBadge({ status }: { status: TicketStatus }) {
  return <span className={`status-badge status-${status.replaceAll("_", "-")}`}>{statusLabels[status]}</span>;
}

function ErrorPanel({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="ticket-error" role="alert"><p>{message}</p>{onRetry && <button className="text-button" type="button" onClick={onRetry}>Try again</button>}</div>;
}

function ticketErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "We could not reach your requests. Check your connection and try again.";
}

function CustomerShell({ children, hasUnsavedDraft = false }: { children: ReactNode; current: "dashboard" | "tickets"; hasUnsavedDraft?: boolean }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [logoutError, setLogoutError] = useState("");

  async function signOut() {
    setLogoutError("");
    if (hasUnsavedDraft && !window.confirm("You have an unsent reply. Sign out and discard it?")) return;
    try {
      await logout();
      navigate("/", { replace: true });
    } catch {
      setLogoutError("We could not sign you out. Please try again.");
    }
  }

  return (
    <main className="customer-app">
      <header className="customer-topbar">
        <Link className="brand" to="/app/dashboard" aria-label="CaseFlow dashboard"><span className="brand-mark-small">C</span><span>caseflow</span></Link>
        <div className="customer-account"><span className="customer-greeting">{user?.full_name}</span><button className="text-button" type="button" onClick={signOut}>Sign out</button></div>
      </header>
      <div className="customer-body">
        <aside className="customer-sidebar" aria-label="Customer workspace">
          <p className="sidebar-eyebrow">YOUR SPACE</p>
          <nav className="workspace-nav" aria-label="Workspace navigation">
            <NavLink to="/app/dashboard" className={({ isActive }) => isActive ? "workspace-link active" : "workspace-link"}>Overview</NavLink>
            <NavLink to="/app/tickets" className={({ isActive }) => isActive ? "workspace-link active" : "workspace-link"}>My requests</NavLink>
          </nav>
          <Link className="sidebar-create" to="/app/tickets/new">＋ New request</Link>
        </aside>
        <section className="customer-main" aria-label="Customer content">
          {logoutError && <ErrorPanel message={logoutError} />}
          {children}
        </section>
      </div>
    </main>
  );
}

export function CustomerDashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const loadSummary = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      setSummary(await getDashboardSummary());
    } catch (cause) {
      setError(ticketErrorMessage(cause));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Loads the signed-in customer's server-owned request summary.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadSummary();
  }, [loadSummary]);

  return (
    <CustomerShell current="dashboard">
      <div className="page-heading"><div><span className="auth-kicker">NORTHSTAR SERVICES · SUPPORT DESK</span><h1>Your overview</h1><p>Everything you have asked us about, in one place.</p></div><Link className="button button-primary" to="/app/tickets/new">＋ New request</Link></div>
      {loading && <div className="ticket-loading" role="status">Loading your overview…</div>}
      {error && <ErrorPanel message={error} onRetry={() => void loadSummary()} />}
      {!loading && !error && summary && <>
        <div className="count-grid" aria-label="Request counts">
          <CountCard label="Open" count={summary.ticket_counts.open} status="open" />
          <CountCard label="In progress" count={summary.ticket_counts.in_progress} status="in_progress" />
          <CountCard label="Waiting for you" count={summary.ticket_counts.waiting_customer} status="waiting_customer" />
          <CountCard label="Resolved" count={summary.ticket_counts.resolved} status="resolved" />
        </div>
        <section className="panel-section" aria-labelledby="recent-title">
          <div className="panel-heading"><div><h2 id="recent-title">Recent requests</h2><p>{summary.total_tickets === 1 ? "1 request in your space" : `${summary.total_tickets} requests in your space`}</p></div><Link to="/app/tickets">View all <span aria-hidden="true">→</span></Link></div>
          {summary.recent_tickets.length ? <TicketRows tickets={summary.recent_tickets} /> : <EmptyTickets />}
        </section>
      </>}
    </CustomerShell>
  );
}

function CountCard({ label, count, status }: { label: string; count: number; status: TicketStatus }) {
  return <article className="count-card"><span className={`count-indicator status-${status.replaceAll("_", "-")}`} /><p>{label}</p><strong>{count}</strong></article>;
}

function EmptyTickets() {
  return <div className="empty-state"><span className="empty-symbol" aria-hidden="true">✳</span><h3>No requests yet</h3><p>When you ask for help, your request and replies will show up here.</p><Link className="button button-primary" to="/app/tickets/new">Create your first request</Link></div>;
}

function TicketRows({ tickets }: { tickets: TicketSummary[] }) {
  return <div className="ticket-rows" role="list" aria-label="Support requests">
    {tickets.map((ticket) => <Link className="ticket-row" role="listitem" key={ticket.id} to={`/app/tickets/${ticket.id}`}>
      <div className="ticket-row-main"><span className="ticket-ref">{ticket.reference}</span><h3>{ticket.subject}</h3><span className="ticket-category">{categoryLabels[ticket.category]}</span></div>
      <StatusBadge status={ticket.status} />
      <time className="ticket-row-date" dateTime={ticket.updated_at}>{displayDate(ticket.updated_at)}</time>
      <span className="ticket-row-arrow" aria-hidden="true">→</span>
    </Link>)}
  </div>;
}

export function CustomerTicketList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [queryDraft, setQueryDraft] = useState(searchParams.get("q") ?? "");
  const [data, setData] = useState<TicketPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const page = Number(searchParams.get("page") ?? "1");

  const loadTickets = useCallback(async () => {
    setError("");
    setLoading(true);
    const params = new URLSearchParams(searchParams);
    params.set("page", String(page));
    params.set("page_size", "20");
    try {
      setData(await getTickets(params));
    } catch (cause) {
      setError(ticketErrorMessage(cause));
    } finally {
      setLoading(false);
    }
  }, [page, searchParams]);

  useEffect(() => {
    // Keeps filtering and pagination tied to the URL for browser Back support.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadTickets();
  }, [loadTickets]);

  function applyFilter(key: "status" | "category", value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    next.delete("page");
    setSearchParams(next);
  }

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = new URLSearchParams(searchParams);
    if (queryDraft.trim()) next.set("q", queryDraft.trim());
    else next.delete("q");
    next.delete("page");
    setSearchParams(next);
  }

  function goToPage(targetPage: number) {
    const next = new URLSearchParams(searchParams);
    if (targetPage > 1) next.set("page", String(targetPage));
    else next.delete("page");
    setSearchParams(next);
  }

  return (
    <CustomerShell current="tickets">
      <div className="page-heading"><div><span className="auth-kicker">YOUR SUPPORT HISTORY</span><h1>My requests</h1><p>Follow replies and see the next step for each request.</p></div><Link className="button button-primary" to="/app/tickets/new">＋ New request</Link></div>
      <section className="filter-panel" aria-label="Filter support requests">
        <form className="ticket-search" onSubmit={search}><label htmlFor="ticket-search">Search requests</label><div><input id="ticket-search" type="search" minLength={2} maxLength={100} value={queryDraft} onChange={(event) => setQueryDraft(event.target.value)} placeholder="Subject or reference" /><button className="filter-button" type="submit">Search</button></div></form>
        <label className="filter-field">Status<select value={searchParams.get("status") ?? ""} onChange={(event) => applyFilter("status", event.target.value)}><option value="">All statuses</option>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label className="filter-field">Category<select value={searchParams.get("category") ?? ""} onChange={(event) => applyFilter("category", event.target.value)}><option value="">All categories</option>{Object.entries(categoryLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      </section>
      {loading && <div className="ticket-loading" role="status">Loading your requests…</div>}
      {error && <ErrorPanel message={error} onRetry={() => void loadTickets()} />}
      {!loading && !error && data && (data.items.length ? <>
        <p className="results-count" aria-live="polite">{data.pagination.total_items} {data.pagination.total_items === 1 ? "request" : "requests"}</p>
        <TicketRows tickets={data.items} />
        {data.pagination.total_pages > 1 && <nav className="pagination-nav" aria-label="Request pages"><button className="filter-button" type="button" disabled={page <= 1} onClick={() => goToPage(page - 1)}>Previous</button><span>Page {page} of {data.pagination.total_pages}</span><button className="filter-button" type="button" disabled={page >= data.pagination.total_pages} onClick={() => goToPage(page + 1)}>Next</button></nav>}
      </> : <EmptyTickets />)}
    </CustomerShell>
  );
}

export function CustomerTicketCreate() {
  const navigate = useNavigate();
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<TicketCategory>("general");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const ticket = await createTicket({ subject, description, category });
      navigate(`/app/tickets/${ticket.id}`, { replace: true });
    } catch (cause) {
      setError(ticketErrorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  return <CustomerShell current="tickets"><div className="page-heading"><div><span className="auth-kicker">TELL US WHAT’S GOING ON</span><h1>New request</h1><p>Share a few details so we can understand how to help.</p></div></div>
    <div className="ticket-form-card"><form className="ticket-form" onSubmit={submit}>
      <label htmlFor="request-subject">Subject<input id="request-subject" required minLength={8} maxLength={150} value={subject} onChange={(event) => setSubject(event.target.value)} placeholder="A short summary of the issue" /><small>{subject.length}/150 characters</small></label>
      <label htmlFor="request-category">Category<select id="request-category" required value={category} onChange={(event) => setCategory(event.target.value as TicketCategory)}>{Object.entries(categoryLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label htmlFor="request-description">What happened?<textarea id="request-description" required minLength={30} maxLength={5000} rows={7} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Include what you were trying to do and what you saw." /><small>{description.length}/5000 characters · Please do not include passwords or real financial details.</small></label>
      {error && <ErrorPanel message={error} />}
      <div className="ticket-form-actions"><Link className="button button-quiet" to="/app/tickets">Cancel</Link><button className="button button-primary" type="submit" disabled={busy}>{busy ? "Sending…" : "Submit request"}</button></div>
    </form></div>
  </CustomerShell>;
}

export function CustomerTicketDetail() {
  const { ticketId = "" } = useParams();
  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reply, setReply] = useState("");
  const [replyError, setReplyError] = useState("");
  const [sending, setSending] = useState(false);
  const [reopenReason, setReopenReason] = useState("");
  const [reopenError, setReopenError] = useState("");
  const [reopening, setReopening] = useState(false);
  const [showReopen, setShowReopen] = useState(false);
  const [canReopen, setCanReopen] = useState(false);

  const loadTicket = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [detail, activity] = await Promise.all([getTicket(ticketId), getTicketTimeline(ticketId)]);
      setTicket(detail);
      setTimeline(activity.items);
    } catch (cause) {
      setError(ticketErrorMessage(cause));
    } finally {
      setLoading(false);
    }
  }, [ticketId]);

  useEffect(() => {
    // Loads the ticket and its owner-scoped, public timeline.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadTicket();
  }, [loadTicket]);

  useEffect(() => {
    // The seven-day window depends on the clock when the response arrives.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCanReopen(ticket?.status === "resolved" && ticket.resolved_at !== null &&
      Date.now() - new Date(ticket.resolved_at).getTime() <= 7 * 24 * 60 * 60 * 1000);
  }, [ticket]);

  async function sendReply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setReplyError("");
    setSending(true);
    try {
      const created = await addTicketReply(ticketId, reply);
      setTimeline((items) => [...items, created].sort((left, right) => left.created_at.localeCompare(right.created_at) || left.id.localeCompare(right.id)));
      setReply("");
      if (ticket) setTicket({
        ...ticket,
        status: ticket.status === "waiting_customer" ? "in_progress" : ticket.status,
        updated_at: created.created_at,
      });
    } catch (cause) {
      setReplyError(ticketErrorMessage(cause));
    } finally {
      setSending(false);
    }
  }

  async function submitReopen(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setReopenError("");
    setReopening(true);
    try {
      await reopenCustomerTicket(ticketId, reopenReason);
      setReopenReason("");
      setShowReopen(false);
      await loadTicket();
    } catch (cause) {
      setReopenError(ticketErrorMessage(cause));
    } finally {
      setReopening(false);
    }
  }

  const canReply = ticket !== null && ticket.status !== "resolved" && ticket.status !== "closed";
  return <CustomerShell current="tickets" hasUnsavedDraft={Boolean(reply.trim() || reopenReason.trim())}><div className="detail-back"><Link to="/app/tickets">← My requests</Link></div>
    {loading && <div className="ticket-loading" role="status">Loading this request…</div>}
    {error && <ErrorPanel message={error} onRetry={() => void loadTicket()} />}
    {!loading && !error && ticket && <>
      <div className="ticket-detail-heading"><div><span className="ticket-ref">{ticket.reference} · {categoryLabels[ticket.category]}</span><h1>{ticket.subject}</h1><p>Created {displayDate(ticket.created_at)}</p></div><StatusBadge status={ticket.status} /></div>
      <section className="ticket-detail-grid">
        <div className="ticket-detail-primary">
          <article className="ticket-description-card"><div className="section-label">YOUR REQUEST</div><p>{ticket.description}</p></article>
          <section className="timeline-card" aria-labelledby="timeline-heading"><div className="section-label" id="timeline-heading">CONVERSATION & ACTIVITY</div>
            {timeline.length === 0 ? <p className="timeline-empty">There is no activity yet.</p> : <ol className="timeline-list">{timeline.map((item) => <TimelineEntry key={item.id} item={item} />)}</ol>}
          </section>
          {canReopen && !showReopen && <div className="reopen-card"><div><strong>Still need help?</strong><p>You can reopen this resolved request within seven days.</p></div><button className="filter-button" type="button" onClick={() => setShowReopen(true)}>Reopen request</button></div>}
          {canReopen && showReopen && <form className="reply-card" onSubmit={submitReopen}><label htmlFor="reopen-reason">What still needs attention?<textarea id="reopen-reason" required minLength={10} maxLength={3000} rows={4} value={reopenReason} onChange={(event) => setReopenReason(event.target.value)} placeholder="Tell us what happened after the request was resolved" /></label><div className="reply-footer"><small>{reopenReason.length}/3000 · Shared with the support team</small><button className="button button-primary" type="submit" disabled={reopening || reopenReason.trim().length < 10}>{reopening ? "Reopening…" : "Send and reopen"}</button></div>{reopenError && <ErrorPanel message={reopenError} />}</form>}
          {canReply && <form className="reply-card" onSubmit={sendReply}><label htmlFor="customer-reply">Add a reply<textarea id="customer-reply" required minLength={1} maxLength={3000} rows={4} value={reply} onChange={(event) => setReply(event.target.value)} placeholder="Write a message to the support team" /></label><div className="reply-footer"><small>{reply.length}/3000 · Visible to you and the support team</small><button className="button button-primary" type="submit" disabled={sending || !reply.trim()}>{sending ? "Sending…" : "Send reply"}</button></div>{replyError && <ErrorPanel message={replyError} />}</form>}
          {ticket.status === "resolved" && !canReopen && <div className="closed-notice">This request is resolved and its seven-day reopening window has ended.</div>}
          {ticket.status === "closed" && <div className="closed-notice">This request is closed. Replies and reopening are unavailable.</div>}
        </div>
        <aside className="ticket-detail-aside"><div className="section-label">REQUEST DETAILS</div><dl><dt>Reference</dt><dd>{ticket.reference}</dd><dt>Category</dt><dd>{categoryLabels[ticket.category]}</dd><dt>Priority</dt><dd className="priority-value">{ticket.priority.charAt(0).toUpperCase() + ticket.priority.slice(1)}</dd><dt>Last updated</dt><dd>{displayDate(ticket.updated_at)}</dd></dl><div className="aside-note">Replies and updates to this request stay together here.</div></aside>
      </section>
    </>}
  </CustomerShell>;
}

function TimelineEntry({ item }: { item: TimelineItem }) {
  return <li className={`timeline-entry timeline-${item.kind}`}><span className="timeline-marker" aria-hidden="true">{item.kind === "message" ? item.actor_name.slice(0, 1).toUpperCase() : "✓"}</span><div className="timeline-entry-content"><div className="timeline-entry-meta"><strong>{item.kind === "message" ? item.actor_name : item.summary}</strong><time dateTime={item.created_at}>{displayDate(item.created_at)}</time></div>{item.body && <p>{item.body}</p>}</div></li>;
}
