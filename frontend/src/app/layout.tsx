import type { Metadata } from "next";
import type { ReactNode } from "react";
import "@/styles/globals.css";
import AppSidebar from "@/components/layout/AppSidebar";
import { NavigationProvider } from "@/components/common/NavigationProvider";
import { ThemeProvider } from "@/components/common/ThemeProvider";
import { Toaster } from "@/components/ui/sonner";
import { SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";

export const metadata: Metadata = {
  title: "RenderHive",
  description: "Next-Gen Render Farm Management Engine",
};

interface RootLayoutProps {
  children: ReactNode;
}

const themeScript = `
(() => {
  try {
    const storageKey = "renderhive-theme";
    const storedTheme = window.localStorage.getItem(storageKey);
    const theme = storedTheme === "light" || storedTheme === "dark" ? storedTheme : "dark";
    const root = document.documentElement;
    root.classList.remove("light", "dark");
    root.classList.add(theme);
    root.style.colorScheme = theme;
  } catch {
    document.documentElement.classList.add("dark");
  }
})();
`;

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="flex min-h-screen bg-background text-foreground">
        <ThemeProvider>
          <TooltipProvider>
            <NavigationProvider>
              <SidebarProvider>
                <AppSidebar />
                <main className="flex-1 flex flex-col min-w-0">{children}</main>
              </SidebarProvider>
            </NavigationProvider>
          </TooltipProvider>
        </ThemeProvider>
        <Toaster />
      </body>
    </html>
  );
}
