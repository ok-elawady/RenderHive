import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import AppSidebar from "./components/AppSidebar";
import { NavigationProvider } from "./components/NavigationProvider";
import { ThemeProvider } from "./components/ThemeProvider";

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
      <body className="flex min-h-screen bg-[#F7F8FA] text-[#1A1D23] dark:bg-[#0E1016] dark:text-[#F5F7FA]">
        <ThemeProvider>
          <NavigationProvider>
            <AppSidebar />
            <main className="flex-1 flex flex-col min-w-0">{children}</main>
          </NavigationProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
