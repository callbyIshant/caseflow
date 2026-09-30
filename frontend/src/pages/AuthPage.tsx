import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

function destination(next: string | null, role: string): string {
  if (next?.startsWith("/") && !next.startsWith("//")) return next;
  return role === "customer" ? "/app" : "/agent";
}

export function AuthPage({ mode }: { mode: "login" | "register" }) {
  const isRegister = mode === "register";
  const { user, loading, login, register } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const next = new URLSearchParams(location.search).get("next");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (loading) return <main className="auth-loading" aria-live="polite">Checking your session…</main>;
  if (user) return <Navigate to={destination(next, user.role)} replace />;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (isRegister && password !== confirmPassword) {
      setError("Those passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      const signedInUser = isRegister
        ? await register(fullName, email, password)
        : await login(email, password);
      navigate(destination(next, signedInUser.role), { replace: true });
    } catch (cause) {
      if (cause instanceof ApiError) setError(cause.message);
      else setError("We could not reach CaseFlow. Check your connection and try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-brand-row">
        <Link className="brand" to="/"><span className="brand-mark-small">C</span><span>caseflow</span></Link>
        <Link className="auth-back" to="/">Back to home</Link>
      </div>
      <section className="auth-card" aria-labelledby="auth-title">
        <span className="auth-kicker">NORTHSTAR SERVICES · SUPPORT DESK</span>
        <h1 id="auth-title">{isRegister ? "Create your account" : "Welcome back"}</h1>
        <p className="auth-intro">{isRegister ? "Keep your requests and replies together in one clear place." : "Sign in to pick up where your support conversation left off."}</p>
        <form onSubmit={submit}>
          {isRegister && <label htmlFor="full-name">Full name<input id="full-name" name="name" autoComplete="name" required minLength={2} maxLength={100} value={fullName} onChange={(event) => setFullName(event.target.value)} /></label>}
          <label htmlFor="email">Email address<input id="email" name="email" type="email" autoComplete="email" required maxLength={254} value={email} onChange={(event) => setEmail(event.target.value)} /></label>
          <label htmlFor="password">Password<input id="password" name="password" type="password" autoComplete={isRegister ? "new-password" : "current-password"} required minLength={isRegister ? 12 : 1} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} />{isRegister && <small>Use at least 12 characters. Spaces are welcome.</small>}</label>
          {isRegister && <label htmlFor="confirm-password">Confirm password<input id="confirm-password" name="confirmPassword" type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} /></label>}
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="button button-primary auth-submit" type="submit" disabled={busy}>{busy ? "Please wait…" : isRegister ? "Create account" : "Sign in"}</button>
        </form>
        <p className="auth-switch">{isRegister ? "Already have an account?" : "New to CaseFlow?"} <Link to={isRegister ? "/login" : "/register"}>{isRegister ? "Sign in" : "Create an account"}</Link></p>
        <p className="auth-disclaimer">Portfolio demonstration only. Use fictional information, not real support or financial account details.</p>
      </section>
    </main>
  );
}

export function CustomerHome() {
  return <SignedInHome audience="Customer workspace" />;
}

export function StaffHome() {
  return <SignedInHome audience="Support workspace" />;
}

function SignedInHome({ audience }: { audience: string }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  async function signOut() {
    try {
      await logout();
      navigate("/", { replace: true });
    } catch {
      setError("We could not sign you out. Please try again.");
    }
  }

  return (
    <main className="workspace-page">
      <header className="workspace-bar"><Link className="brand" to="/"><span className="brand-mark-small">C</span><span>caseflow</span></Link><button className="text-button" type="button" onClick={signOut}>Sign out</button></header>
      <section className="workspace-card"><span className="auth-kicker">NORTHSTAR SERVICES · SUPPORT DESK</span><h1>{audience}</h1><p>You’re signed in as <strong>{user?.full_name}</strong>.</p><p className="workspace-next">Your account is ready. The request workspace is coming next.</p>{error && <p role="alert" className="form-error">{error}</p>}</section>
    </main>
  );
}
