import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

type DemoTicket = {
  id: string;
  reference: string;
  subject: string;
  category: string;
  status: string;
  statusTone: "blue" | "amber" | "green";
  updated: string;
  description: string;
  activity: { actor: string; time: string; body: string; kind: "customer" | "support" | "event" }[];
};

const demoTickets: DemoTicket[] = [
  {
    id: "profile",
    reference: "CF-000184",
    subject: "Profile changes are not appearing yet",
    category: "Account access",
    status: "In progress",
    statusTone: "blue",
    updated: "Updated 12 min ago",
    description: "I saved a change to my contact preferences, but the page still shows the old setting when I return. I signed out and back in, and the details are still the same.",
    activity: [
      { actor: "Jordan Lee", time: "Today · 10:14 AM", body: "I saved a change to my contact preferences, but the page still shows the old setting when I return.", kind: "customer" },
      { actor: "Request submitted", time: "Today · 10:14 AM", body: "The support team has your request.", kind: "event" },
      { actor: "Northstar Support", time: "Today · 10:26 AM", body: "Thanks for letting us know. We’re checking how that preference is being saved and will update you here.", kind: "support" },
    ],
  },
  {
    id: "statement",
    reference: "CF-000179",
    subject: "Where can I find last month’s statement?",
    category: "General question",
    status: "Waiting for you",
    statusTone: "amber",
    updated: "Updated yesterday",
    description: "I’m looking for a copy of last month’s sample statement in the demo workspace. Could you point me to the right place?",
    activity: [
      { actor: "Jordan Lee", time: "Yesterday · 2:32 PM", body: "I’m looking for a copy of last month’s sample statement in the demo workspace.", kind: "customer" },
      { actor: "Northstar Support", time: "Yesterday · 2:48 PM", body: "You can find sample documents under Documents in your workspace. Does that help?", kind: "support" },
      { actor: "We’re waiting for a reply", time: "Yesterday · 2:48 PM", body: "Reply to continue the conversation.", kind: "event" },
    ],
  },
  {
    id: "resolved",
    reference: "CF-000166",
    subject: "A saved search is missing from my list",
    category: "Technical help",
    status: "Resolved",
    statusTone: "green",
    updated: "Updated Monday",
    description: "One of my saved searches disappeared after I changed its name. I was able to recreate the search, but wanted to check whether the original can be restored.",
    activity: [
      { actor: "Jordan Lee", time: "Monday · 9:05 AM", body: "One of my saved searches disappeared after I changed its name.", kind: "customer" },
      { actor: "Northstar Support", time: "Monday · 9:41 AM", body: "We found the original search and restored it to your list. Your recreated copy is still there too, so you can remove either one.", kind: "support" },
      { actor: "Request resolved", time: "Monday · 9:41 AM", body: "A resolution was shared with the customer.", kind: "event" },
    ],
  },
];
function getInitialDemoTicket(): DemoTicket {
  const ticket = demoTickets[0];
  if (!ticket) throw new Error("The read-only tour requires at least one fixed example.");
  return ticket;
}
const initialDemoTicket: DemoTicket = getInitialDemoTicket();

export function DemoPage() {
  const [selectedId, setSelectedId] = useState(initialDemoTicket.id);
  const selected = demoTickets.find((ticket) => ticket.id === selectedId) ?? initialDemoTicket;

  return (
    <main className="demo-page">
      <header className="demo-topbar">
        <Link className="brand" to="/" aria-label="CaseFlow home"><span className="brand-mark-small">C</span><span>caseflow</span></Link>
        <nav aria-label="Demo navigation"><Link to="/">Home</Link><Link className="button button-primary" to="/register">Create account</Link></nav>
      </header>
      <section className="demo-intro" aria-labelledby="demo-title">
        <span className="auth-kicker">A READ-ONLY PRODUCT TOUR</span>
        <h1 id="demo-title">A clearer view of every request.</h1>
        <p>Explore a fixed set of fictional examples. Nothing here connects to the live ticket system.</p>
        <div className="demo-disclaimer"><span aria-hidden="true">✳</span><span><strong>Portfolio demo</strong> · Names, messages and request details below are synthetic.</span></div>
      </section>
      <section className="demo-workspace" aria-label="Synthetic customer workspace preview">
        <aside className="demo-request-list" aria-label="Example requests">
          <div className="demo-list-heading"><div><span className="section-kicker">YOUR SPACE</span><h2>My requests</h2></div><span className="demo-count">03</span></div>
          <div className="demo-request-options">
            {demoTickets.map((ticket) => (
              <button
                type="button"
                className={`demo-request-option${selected.id === ticket.id ? " selected" : ""}`}
                key={ticket.id}
                aria-current={selected.id === ticket.id ? "true" : undefined}
                onClick={() => setSelectedId(ticket.id)}
              >
                <span className="demo-option-ref">{ticket.reference}</span>
                <strong>{ticket.subject}</strong>
                <span className={`demo-status demo-status-${ticket.statusTone}`}>{ticket.status}</span>
                <span className="demo-option-updated">{ticket.updated}</span>
              </button>
            ))}
          </div>
        </aside>
        <article className="demo-request-detail" aria-live="polite" aria-labelledby="demo-ticket-title">
          <div className="demo-detail-heading">
            <div><Link className="demo-back-link" to="/">← CaseFlow overview</Link><span className="demo-option-ref">{selected.reference} · {selected.category}</span><h2 id="demo-ticket-title">{selected.subject}</h2><span className={`demo-status demo-status-${selected.statusTone}`}>{selected.status}</span></div>
          </div>
          <div className="demo-description"><span className="section-label">REQUEST DETAILS</span><p>{selected.description}</p></div>
          <section className="demo-conversation" aria-labelledby="demo-conversation-title">
            <div className="demo-conversation-heading"><span className="section-label" id="demo-conversation-title">CONVERSATION & ACTIVITY</span><span>{selected.activity.length} updates</span></div>
            <ol className="timeline-list">
              {selected.activity.map((item, index) => (
                <li className={`timeline-entry timeline-${item.kind === "event" ? "event" : "message"}`} key={`${selected.id}-${index}`}>
                  <span className="timeline-marker" aria-hidden="true">{item.kind === "event" ? "✓" : item.actor.slice(0, 1)}</span>
                  <div className="timeline-entry-content"><div className="timeline-entry-meta"><strong>{item.actor}</strong><time>{item.time}</time></div><p>{item.body}</p></div>
                </li>
              ))}
            </ol>
          </section>
          <div className="demo-readonly-message"><span aria-hidden="true">◉</span><p><strong>This preview is read-only.</strong><br />Sign in to create a request and continue a real support conversation.</p><Link to="/register">Get started <span aria-hidden="true">→</span></Link></div>
        </article>
      </section>
      <footer className="demo-footer"><span>Northstar Services is fictional.</span><Link to="/">Back to CaseFlow</Link></footer>
    </main>
  );
}

export function NotFoundPage() {
  return (
    <main className="not-found-page">
      <Link className="brand" to="/" aria-label="CaseFlow home"><span className="brand-mark-small">C</span><span>caseflow</span></Link>
      <section aria-labelledby="not-found-title"><span className="not-found-code">404</span><h1 id="not-found-title">We can’t find that page.</h1><p>The address may have changed, or the link may be incomplete.</p><div><Link className="button button-primary" to="/">Back to home</Link><Link className="button button-quiet" to="/demo">Explore the demo</Link></div></section>
    </main>
  );
}

export function ForbiddenPage() {
  const { user } = useAuth();
  const destination = user?.role === "customer" ? "/app/dashboard" : "/agent/queue";
  const destinationLabel = user?.role === "customer" ? "Return to your requests" : "Return to the shared queue";
  return (
    <main className="not-found-page">
      <Link className="brand" to="/" aria-label="CaseFlow home"><span className="brand-mark-small">C</span><span>caseflow</span></Link>
      <section aria-labelledby="forbidden-title"><span className="not-found-code">ACCESS DENIED</span><h1 id="forbidden-title">This workspace is not available to your account.</h1><p>Your account does not have access to that area. You can return to the workspace available to you.</p><div><Link className="button button-primary" to={destination}>{destinationLabel}</Link></div></section>
    </main>
  );
}
