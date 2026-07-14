"use client";

import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { DashboardView } from "../types/dashboard";

interface NavigationContextValue {
  activeView: DashboardView;
  setActiveView: (view: DashboardView) => void;
}

interface NavigationProviderProps {
  children: ReactNode;
}

const NavigationContext = createContext<NavigationContextValue | null>(null);

export function NavigationProvider({ children }: NavigationProviderProps) {
  const [activeView, setActiveView] = useState<DashboardView>("Dashboard");

  const value = useMemo<NavigationContextValue>(
    () => ({ activeView, setActiveView }),
    [activeView],
  );

  return (
    <NavigationContext.Provider value={value}>
      {children}
    </NavigationContext.Provider>
  );
}

export function useNavigation(): NavigationContextValue {
  const context = useContext(NavigationContext);

  if (!context) {
    throw new Error("useNavigation must be used inside NavigationProvider");
  }

  return context;
}
