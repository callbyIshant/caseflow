import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function ProtectedRoute({ children, roles }: { children: ReactNode; roles?: string[] }) {
  const { user, loading, justLoggedOut } = useAuth();
  const location = useLocation();
  if (loading) return <main className="auth-loading" aria-live="polite">Checking your session…</main>;
  if (!user) {
    if (justLoggedOut) return <Navigate to="/" replace />;
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }
  if (roles && !roles.includes(user.role)) {
    return <Navigate to={user.role === "customer" ? "/app" : "/agent"} replace />;
  }
  return children;
}
