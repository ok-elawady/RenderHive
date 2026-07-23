"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  clearAuthSession,
  login,
  readAuthSession,
  type AuthSession,
  type AuthUser,
  type LoginCredentials,
} from "@/services/api";

interface AuthContextValue {
  isAuthenticated: boolean;
  isHydrating: boolean;
  isLoggingOut: boolean;
  session: AuthSession | null;
  user: AuthUser | null;
  loginUser: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [isHydrating, setIsHydrating] = useState<boolean>(true);
  const [isLoggingOut, setIsLoggingOut] = useState<boolean>(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSession(readAuthSession());
    setIsHydrating(false);
  }, []);

  const loginUser = useCallback(async (credentials: LoginCredentials): Promise<void> => {
    const nextSession = await login(credentials);
    setSession(nextSession);
  }, []);

  const logout = useCallback((): void => {
    setIsLoggingOut(true);

    window.setTimeout(() => {
      clearAuthSession();
      setSession(null);
      setIsLoggingOut(false);
    }, 650);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      isAuthenticated: Boolean(session),
      isHydrating,
      isLoggingOut,
      session,
      user: session?.user ?? null,
      loginUser,
      logout,
    }),
    [isHydrating, isLoggingOut, loginUser, logout, session],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used inside <AuthProvider>.");
  }

  return context;
}
