"use client";

import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface TableSortHeaderProps {
  label: string;
  sortKey: string;
  currentSortKey?: string | null;
  currentDirection?: "asc" | "desc" | null;
  onSort: (key: string) => void;
  align?: "left" | "center" | "right";
  className?: string;
}

export function TableSortHeader({
  label,
  sortKey,
  currentSortKey,
  currentDirection,
  onSort,
  align = "left",
  className,
}: TableSortHeaderProps) {
  const isSorted = currentSortKey === sortKey;

  const renderIcon = () => {
    if (!isSorted) {
      return <ArrowUpDown className="ml-1.5 size-3.5 opacity-50 group-hover:opacity-100 transition-opacity shrink-0" />;
    }
    if (currentDirection === "asc") {
      return <ArrowUp className="ml-1.5 size-3.5 text-primary shrink-0" />;
    }
    return <ArrowDown className="ml-1.5 size-3.5 text-primary shrink-0" />;
  };

  const alignWrapperClass =
    align === "center"
      ? "flex justify-center w-full"
      : align === "right"
        ? "flex justify-end w-full"
        : "flex justify-start w-full";

  const buttonOffsetClass = align === "left" ? "-ml-3" : align === "right" ? "-mr-3" : "";

  return (
    <div className={alignWrapperClass}>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => onSort(sortKey)}
        className={cn(
          "font-semibold flex items-center group h-8 text-xs text-muted-foreground hover:text-foreground",
          buttonOffsetClass,
          className,
        )}
      >
        <span>{label}</span>
        {renderIcon()}
      </Button>
    </div>
  );
}
