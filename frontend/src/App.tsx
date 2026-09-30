function Mark() {
  return (
    <svg aria-hidden="true" viewBox="0 0 36 36" className="brand-mark">
      <rect x="1" y="1" width="34" height="34" rx="11" fill="currentColor" />
      <path d="M11 12.5h14M11 18h10M11 23.5h7" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" />
      <circle cx="25" cy="23.5" r="2" fill="#8dd7cc" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" className="arrow-icon">
      <path d="M3.5 10h12m-5-5 5 5-5 5" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function LandingPage() {
  return (
    <main>
      <header className="topbar">
        <a className="brand" href="#top" aria-label="CaseFlow home">
          <Mark />
          <span>caseflow</span>
        </a>
        <nav className="topnav" aria-label="Main navigation">
          <a href="#workflow">How it works</a>
          <a href="#principles">Built with care</a>
        </nav>
        <div className="nav-actions"><Link className="nav-login" to="/login">Sign in</Link><Link className="nav-cta" to="/register">Create account <ArrowIcon /></Link></div>
      </header>

      <section className="hero" id="top" aria-labelledby="hero-title">
        <div className="hero-copy">
          <div className="eyebrow"><span className="eyebrow-dot" /> NORTHSTAR SERVICES · SUPPORT DESK</div>
          <h1 id="hero-title">Good support starts with a clearer picture.</h1>
          <p className="hero-lede">
            CaseFlow gives every customer request a thoughtful next step — and gives support teams the context to make it count.
          </p>
          <div className="hero-actions">
            <Link className="button button-primary" to="/demo">Explore the demo <ArrowIcon /></Link>
            <Link className="button button-quiet" to="/register">Create an account</Link>
          </div>
          <p className="demo-note"><span className="note-check">✓</span> A portfolio project with fictional, synthetic data.</p>
        </div>
        <div className="hero-art" aria-label="Illustration of a support request moving through a clear workflow">
          <div className="art-glow" />
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="orbit orbit-three" />
          <div className="art-card art-card-back">
            <span className="art-label">A CUSTOMER REPLIED</span>
            <span className="back-line back-line-long" /><span className="back-line back-line-short" />
          </div>
          <div className="art-card art-card-main">
            <div className="request-top"><span className="request-icon">✳</span><span className="request-ref">A little more context</span><span className="request-status"><i /> In progress</span></div>
            <div className="request-title">One conversation, all in one place.</div>
            <div className="request-line"><span className="avatar avatar-teal">N</span><span className="line-body"><b>Northstar support</b><small>Ready for the next step</small></span><span className="line-check">✓</span></div>
            <div className="request-line"><span className="avatar avatar-peach">C</span><span className="line-body"><b>Customer update</b><small>Visible to the right people</small></span><span className="line-clock">↗</span></div>
            <div className="art-footer"><span className="footer-stem" /><span>Clear ownership. Better follow-through.</span></div>
          </div>
          <div className="art-card art-card-note"><span className="note-shape">↗</span><span><b>Next step</b><small>Easy to see</small></span></div>
          <div className="art-orbit-dot dot-a" /><div className="art-orbit-dot dot-b" /><div className="art-orbit-dot dot-c" />
        </div>
      </section>

      <section className="trust-strip" aria-label="CaseFlow principles">
        <p>MADE FOR SUPPORT THAT FEELS HUMAN</p>
        <div><span className="strip-symbol">◎</span> One shared picture</div>
        <div><span className="strip-symbol">◷</span> Thoughtful follow-through</div>
        <div><span className="strip-symbol">◈</span> The right details, kept private</div>
      </section>

      <section className="workflow-section" id="workflow" aria-labelledby="workflow-title">
        <div className="section-heading">
          <span className="section-kicker">A CALMER WAY TO HELP</span>
          <h2 id="workflow-title">From first note to clear resolution.</h2>
          <p>Every request follows a simple, visible path. Customers know where things stand; the team knows what to do next.</p>
        </div>
        <div className="steps">
          <article className="step-card">
            <span className="step-number">01</span>
            <div className="step-icon icon-blue"><span>＋</span></div>
            <h3>Tell us what’s going on</h3>
            <p>Customers share the details that matter and keep the conversation close at hand.</p>
          </article>
          <span className="step-connector" aria-hidden="true">··········›</span>
          <article className="step-card">
            <span className="step-number">02</span>
            <div className="step-icon icon-green"><span>↗</span></div>
            <h3>The right person picks it up</h3>
            <p>Support sees the shared queue, claims a request, and keeps internal notes private.</p>
          </article>
          <span className="step-connector" aria-hidden="true">··········›</span>
          <article className="step-card">
            <span className="step-number">03</span>
            <div className="step-icon icon-lilac"><span>✓</span></div>
            <h3>Every next step is clear</h3>
            <p>Replies and status changes stay together, so the customer is never left guessing.</p>
          </article>
        </div>
      </section>

      <section className="principles-section" id="principles" aria-labelledby="principles-title">
        <div>
          <span className="section-kicker">BUILT WITH CARE</span>
          <h2 id="principles-title">Helpful by design.<br />Private by default.</h2>
        </div>
        <div className="principle-list">
          <article><span className="principle-number">01</span><div><h3>Only the right people see each detail.</h3><p>Customer requests are scoped to their owner. Internal support notes stay on the support side.</p></div></article>
          <article><span className="principle-number">02</span><div><h3>Every important change leaves a trail.</h3><p>Replies, ownership and status move together with a clear activity history.</p></div></article>
          <article><span className="principle-number">03</span><div><h3>Small, dependable building blocks.</h3><p>A single web app and PostgreSQL keep the workflow easy to reason about and maintain.</p></div></article>
        </div>
      </section>

      <footer className="footer">
        <a className="brand footer-brand" href="#top"><Mark /><span>caseflow</span></a>
        <p>Northstar Services is fictional. CaseFlow is a portfolio demonstration and is not affiliated with any financial institution.</p>
        <span className="footer-status"><i /> Designed for clarity</span>
      </footer>
    </main>
  );
}
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthProvider";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { AuthPage, CustomerHome, StaffHome } from "./pages/AuthPage";


function DemoPreview() {
  return <main className="workspace-page"><header className="workspace-bar"><Link className="brand" to="/"><span className="brand-mark-small">C</span><span>caseflow</span></Link><Link className="text-button" to="/register">Create account</Link></header><section className="workspace-card"><span className="auth-kicker">READ-ONLY PRODUCT TOUR</span><h1>CaseFlow demo</h1><p>The synthetic support queue preview is being prepared.</p><Link className="button button-primary" to="/">Back to home</Link></section></main>;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<AuthPage mode="login" />} />
          <Route path="/register" element={<AuthPage mode="register" />} />
          <Route path="/demo" element={<DemoPreview />} />
          <Route path="/app/*" element={<ProtectedRoute roles={["customer"]}><CustomerHome /></ProtectedRoute>} />
          <Route path="/agent/*" element={<ProtectedRoute roles={["agent", "admin"]}><StaffHome /></ProtectedRoute>} />
          <Route path="*" element={<LandingPage />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
