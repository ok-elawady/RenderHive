"use client";

import { Sun, Moon, Plus } from "lucide-react";
import Link from "next/link";
import { GlobalSearch } from "@/components/layout/GlobalSearch";
import { Button, buttonVariants } from "@/components/ui/button";
import { useTheme } from "@/components/common/ThemeProvider";

export default function TopNav() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <header className="sticky top-0 z-40 flex w-full items-center justify-between border-b border-border bg-background/95 px-6 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="flex items-center gap-6 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-primary animate-pulse"></span>
            <span className="hidden sm:inline">API:</span>{" "}
            <span className="text-foreground">localhost:8000</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-[#9E8EFF]"></span>
            <span className="hidden sm:inline">Polling:</span>{" "}
            <span className="text-foreground">7s</span>
          </div>
        </div>

        <div className="relative flex-1 max-w-md mx-4 md:mx-6">
          <GlobalSearch />
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleTheme}
            aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
            title={isDark ? "Switch to light mode" : "Switch to dark mode"}
            className="group hover:bg-accent/50"
          >
            {isDark ? (
              <Sun
                key="sun"
                size={18}
                className="transition-transform duration-500 group-hover:rotate-45 text-muted-foreground group-hover:text-primary"
              />
            ) : (
              <Moon
                key="moon"
                size={18}
                className="transition-transform duration-500 group-hover:-rotate-12 text-muted-foreground group-hover:text-primary"
              />
            )}
          </Button>

          <Link
            href="/jobs/submit"
            className={`${buttonVariants({ size: "default" })} font-bold px-4 shadow-sm`}
          >
            <Plus size={16} />
            <span className="hidden sm:inline">New Job</span>
          </Link>
        </div>
      </header>
  );
}
