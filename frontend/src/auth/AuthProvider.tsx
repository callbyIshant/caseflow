import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { apiRequest, setCsrfToken, setUnauthorizedHandler } from "../api/client";
import { AuthContext, type User } from "./AuthContext";

type SessionResponse = {
  authenticated: boolean;
  user?: User | null;
  csrf_token?: string | null;
};

type AuthResponse = { user: User; csrf_token: string };
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [justLoggedOut, setJustLoggedOut] = useState(false);

  const handleUnauthorized = useCallback(() => {
    setCsrfToken(null);
    setUser(null);
    setJustLoggedOut(false);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(handleUnauthorized);
    return () => setUnauthorizedHandler(null);
  }, [handleUnauthorized]);

  const refreshSession = useCallback(async () => {
    try {
      const session = await apiRequest<SessionResponse>("/auth/session");
      setCsrfToken(session.authenticated ? session.csrf_token ?? null : null);
      setUser(session.authenticated ? session.user ?? null : null);
      setJustLoggedOut(false);
    } catch {
      setCsrfToken(null);
      setUser(null);
      setJustLoggedOut(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Session bootstrap synchronizes React state with the browser's HttpOnly cookie.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshSession();
  }, [refreshSession]);

  const login = useCallback(async (email: string, password: string): Promise<User> => {
    const result = await apiRequest<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setCsrfToken(result.csrf_token);
    setJustLoggedOut(false);
    setUser(result.user);
    return result.user;
  }, []);

  const register = useCallback(async (fullName: string, email: string, password: string): Promise<User> => {
    const result = await apiRequest<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ full_name: fullName, email, password }),
    });
    setCsrfToken(result.csrf_token);
    setJustLoggedOut(false);
    setUser(result.user);
    return result.user;
  }, []);

  const logout = useCallback(async () => {
    await apiRequest<void>("/auth/logout", { method: "POST" });
    setCsrfToken(null);
    setJustLoggedOut(true);
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, loading, justLoggedOut, login, register, logout }), [user, loading, justLoggedOut, login, register, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
