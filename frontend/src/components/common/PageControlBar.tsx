"use client";

import { ReactNode } from "react";
import { Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export interface FilterChip<T extends string = string> {
  id: T;
  label: string;
  count?: number;
  alert?: boolean;
}

interface PageControlBarProps<T extends string = string> {
  chips?: FilterChip<T>[];
  selectedChip?: T;
  onSelectChip?: (id: T) => void;
  search?: string;
  onSearchChange?: (val: string) => void;
  searchPlaceholder?: string;
  extraRight?: ReactNode;
  className?: string;
}

export function PageControlBar<T extends string = string>({
  chips,
  selectedChip,
  onSelectChip,
  search,
  onSearchChange,
  searchPlaceholder = "Search...",
  extraRight,
  className,
}: PageControlBarProps<T>) {
  return (
    <div className={cn("flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between shrink-0", className)}>
      {/* Left: State Filter Chips or empty container */}
      <div className="flex flex-wrap items-center gap-1.5 overflow-x-auto hide-scrollbar py-0.5">
        {chips?.map((chip) => {
          const isActive = selectedChip === chip.id;
          const hasAlert = chip.alert && !isActive;

          return (
            <Button
              key={chip.id}
              variant={isActive ? "default" : "outline"}
              size="sm"
              onClick={() => onSelectChip?.(chip.id)}
              className={cn(
                "h-8 px-3 text-xs font-mono rounded-lg transition-all border font-medium",
                isActive
                  ? "bg-primary text-primary-foreground border-primary font-semibold shadow-none hover:bg-primary/90 hover:text-primary-foreground"
                  : "bg-card text-muted-foreground border-border hover:bg-muted hover:text-foreground",
                hasAlert && "text-destructive border-destructive/40 bg-destructive/5 hover:bg-destructive/10",
              )}
            >
              <span>{chip.label}</span>
              {chip.count !== undefined && (
                <span
                  className={cn(
                    "ml-1.5 px-1.5 py-0.5 rounded-full text-[11px] font-mono leading-none",
                    isActive
                      ? "bg-primary-foreground/20 text-primary-foreground font-bold"
                      : hasAlert
                        ? "bg-destructive text-destructive-foreground font-bold"
                        : "bg-muted text-muted-foreground",
                  )}
                >
                  {chip.count}
                </span>
              )}
            </Button>
          );
        })}
      </div>

      {/* Right: Standardized Search Input (Right-aligned across all pages), Extra Controls & Counter */}
      <div className="flex items-center gap-2 shrink-0 self-stretch lg:self-auto">
        {onSearchChange !== undefined && (
          <div className="relative min-w-[360px] sm:w-64 flex-1 sm:flex-initial">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground pointer-events-none" />
            <Input
              value={search ?? ""}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder={searchPlaceholder}
              aria-label={searchPlaceholder}
              className="pl-8 pr-8 h-8 text-xs bg-card border-border shadow-none font-sans"
            />
            {search && (
              <button
                type="button"
                onClick={() => onSearchChange("")}
                aria-label="Clear search query"
                className="absolute right-1 top-1/2 -translate-y-1/2 size-6 flex items-center justify-center text-muted-foreground hover:text-foreground cursor-pointer rounded transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <X size={14} />
              </button>
            )}
          </div>
        )}

        {extraRight}
      </div>
    </div>
  );
}
