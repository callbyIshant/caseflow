import { createContext, useContext } from "react";

export type User = {
  id: string;
  full_name: string;
  email: string;
  role: "customer" | "agent" | "admin";
  created_at: string;
};

export type AuthContextValue = {
  user: User | null;
  loading: boolean;
  justLoggedOut: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (fullName: string, email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
};

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider.");
  return context;
}
