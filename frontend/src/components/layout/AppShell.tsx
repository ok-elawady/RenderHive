"use client";

import type { ReactNode } from "react";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/components/auth/AuthProvider";
import LoginPage from "@/components/auth/LoginPage";
import { NavigationProvider } from "@/components/common/NavigationProvider";
import AppSidebar from "@/components/layout/AppSidebar";
import TopNav from "@/components/layout/TopNav";
import { SidebarProvider } from "@/components/ui/sidebar";

export default function AppShell({ children }: { children: ReactNode }) {
  const { isAuthenticated, isHydrating, isLoggingOut } = useAuth();

  if (isHydrating) {
    return (
      <main className="flex min-h-screen flex-1 items-center justify-center bg-background text-muted-foreground font-mono">
        Initializing secure session...
      </main>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return (
    <NavigationProvider>
      <SidebarProvider>
        <AppSidebar />
        <main className="flex flex-1 flex-col min-w-0">
          <TopNav />
          {children}
        </main>
        {isLoggingOut && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center bg-background/90 text-foreground backdrop-blur-md">
            <div className="flex flex-col items-center gap-4 rounded-xl border border-border bg-card px-8 py-7 shadow-2xl shadow-black/40">
              <Loader2 className="animate-spin text-primary" size={32} />
              <div className="text-center font-mono">
                <p className="text-sm font-black">Signing out</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Securing your RenderHive session...
                </p>
              </div>
            </div>
          </div>
        )}
      </SidebarProvider>
    </NavigationProvider>
  );
}
