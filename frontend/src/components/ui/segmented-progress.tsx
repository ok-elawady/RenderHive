import * as React from "react";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { AlertCircle, PlayCircle } from "lucide-react";

interface SegmentedProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  total: number;
  succeeded: number;
  failed: number;
  running: number;
  ready: number;
  waiting: number;
  skipped: number;
  showCounts?: boolean;
}

export function SegmentedProgressBar({
  total,
  succeeded,
  failed,
  running,
  ready,
  waiting,
  skipped,
  className,
  showCounts = false,
  ...props
}: SegmentedProgressProps) {
  // Safe total to avoid division by zero
  const safeTotal = Math.max(total, 1);

  const segments = [
    { key: "succeeded", value: succeeded, color: "bg-success", label: "Succeeded" },
    { key: "running", value: running, color: "bg-info", label: "Running" },
    { key: "failed", value: failed, color: "bg-destructive", label: "Failed" },
    { key: "ready", value: ready, color: "bg-warning", label: "Ready" },
    { key: "waiting", value: waiting, color: "bg-muted-foreground/30", label: "Waiting" },
    { key: "skipped", value: skipped, color: "bg-muted-foreground/10", label: "Skipped" },
  ];

  // Filter out zero-value segments for cleaner rendering, except if total is 0
  const activeSegments = segments.filter((s) => s.value > 0);

  return (
    <Tooltip>
        <TooltipTrigger render={<div className="flex flex-col w-full gap-1" />}>
          <div className={cn("flex h-2 w-full overflow-hidden rounded-full bg-secondary", className)} {...props}>
            {activeSegments.map((segment) => {
              const percentage = (segment.value / safeTotal) * 100;
              return (
                <div
                  key={segment.key}
                  className={cn(
                    "h-full transition-all duration-300 ease-in-out",
                    segment.color,
                  )}
                  style={{ width: `${percentage}%` }}
                />
              );
            })}
          </div>
          {showCounts && (
            <div className="flex items-center gap-2.5 text-xs text-foreground/90 w-full mt-1.5 font-medium">
              <div className="min-w-[2.5rem] font-mono">{(((succeeded + skipped) / safeTotal) * 100).toFixed(0)}%</div>

              {running > 0 && (
                <div className="flex items-center gap-1 text-info bg-info/15 px-2 py-0.5 rounded text-xs font-medium">
                  <PlayCircle size={12} /> {running} Run
                </div>
              )}

              <div className="flex items-center gap-1 text-muted-foreground ml-auto font-mono text-xs">
                {succeeded + skipped} / {total}
              </div>
            </div>
          )}
        </TooltipTrigger>
        <TooltipContent
          side="top"
          className="px-3.5 py-2.5 max-w-none w-auto shadow-xl border border-border bg-popover text-popover-foreground flex items-center rounded-lg z-50"
          arrowClassName="bg-popover fill-popover"
        >
          <div className="flex flex-col justify-center pr-3.5 border-r border-border/60 mr-3.5 shrink-0">
            <span className="text-[9px] font-semibold uppercase tracking-wider text-muted-foreground mb-0.5 whitespace-nowrap">
              Total Tasks
            </span>
            <span className="font-mono text-lg text-foreground font-bold leading-none">{total}</span>
          </div>
          <div className="flex-1 grid grid-cols-2 gap-x-5 gap-y-1.5">
            {segments.map((segment) => {
              const isZero = segment.value === 0;
              return (
                <div
                  key={segment.key}
                  className={cn("flex justify-between items-center min-w-[5.8rem] gap-2", isZero ? "opacity-35" : "")}
                >
                  <div className="flex items-center gap-1.5 shrink-0">
                    <div className={cn("size-1.5 rounded-full shrink-0", segment.color)} />
                    <span className="text-xs text-muted-foreground leading-none">{segment.label}</span>
                  </div>
                  <span className="font-mono text-xs font-semibold text-foreground leading-none">{segment.value}</span>
                </div>
              );
            })}
          </div>
        </TooltipContent>
      </Tooltip>
  );
}
