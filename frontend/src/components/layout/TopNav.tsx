"use client";

import { Sun, Moon, Plus } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { GlobalSearch } from "@/components/layout/GlobalSearch";
import { Button, buttonVariants } from "@/components/ui/button";
import { useTheme } from "@/components/common/ThemeProvider";

export default function TopNav() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <header className="sticky top-0 z-40 flex w-full h-12 items-center justify-between border-b border-border bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex items-center">
        <Link href="/" className="flex items-center gap-2 cursor-pointer pr-4 hover:opacity-80 transition-opacity">
          <div className="relative flex size-6 items-center justify-center shrink-0 transition-all duration-200">
            <Image src="/logo.svg" alt="RenderHive Logo" fill className="object-contain dark:hidden" />
            <Image src="/logo-dark.svg" alt="RenderHive Logo" fill className="object-contain hidden dark:block" />
          </div>
          <div className="flex flex-col gap-0.5 leading-none font-mono">
            <span className="font-black tracking-wider bg-gradient-to-r from-foreground to-muted-foreground bg-clip-text text-transparent">
              Render<span className="text-primary">Hive</span>
            </span>
          </div>
        </Link>
      </div>

        <div className="flex-1" />

        <div className="flex items-center gap-2">
          <GlobalSearch />
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
            className={`${buttonVariants({ size: "sm" })} h-8 font-bold px-4 ml-2 shadow-sm`}
          >
            <Plus size={14} />
            <span className="hidden sm:inline">New Job</span>
          </Link>
        </div>
      </header>
  );
}
