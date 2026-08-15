"use client";

import Link from "next/link";
import { ArrowRight, Cpu, Layers, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { WorkerPool } from "@/services/api";

interface PoolSaturationStripProps {
  pools: WorkerPool[];
  isLoading?: boolean;
}

export function PoolSaturationStrip({ pools, isLoading = false }: PoolSaturationStripProps) {
  if (isLoading) {
    return (
      <Card className="border-border p-0 gap-0">
        <CardHeader className="p-3.5 pb-2.5 border-b border-border/50 flex flex-row items-center justify-between">
          <div className="h-5 w-48 rounded bg-muted/40 animate-pulse" />
        </CardHeader>
        <CardContent className="p-3.5">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="h-20 rounded-lg border border-border/50 bg-muted/20 animate-pulse"
              />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (pools.length === 0) {
    return (
      <Card className="border-dashed border-border/70 p-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary border border-primary/20">
              <Layers size={18} />
            </div>
            <div>
              <p className="text-xs font-bold text-foreground">No Worker Pools Configured</p>
              <p className="text-xs text-muted-foreground">
                Organize worker nodes by hardware tier or department (e.g. GPU Nodes, Lighting Farm) to isolate render workloads.
              </p>
            </div>
          </div>
          <Link
            href="/pools"
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-semibold text-foreground transition-colors hover:bg-accent hover:text-accent-foreground shrink-0"
          >
            <Plus size={13} />
            Configure Pools
          </Link>
        </div>
      </Card>
    );
  }

  return (
    <Card className="border-border p-0 gap-0">
      <CardHeader className="p-3.5 pb-2.5 border-b border-border/50 flex flex-row items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <Layers size={15} className="text-primary" />
          <CardTitle className="text-sm font-bold text-foreground">Worker Pool Saturation</CardTitle>
        </div>
        <Link
          href="/pools"
          className="text-xs font-medium text-muted-foreground hover:text-primary transition-colors flex items-center gap-1 shrink-0 group"
        >
          <span>Manage Pools ({pools.length})</span>
          <ArrowRight size={13} className="transition-transform group-hover:translate-x-0.5" />
        </Link>
      </CardHeader>

      <CardContent className="p-3.5">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {pools.map((pool) => {
            const totalWorkers = pool.worker_count ?? 0;
            const onlineWorkers = pool.online_worker_count ?? 0;
            const renderingWorkers = pool.rendering_worker_count ?? 0;

            const capacityBase = onlineWorkers > 0 ? onlineWorkers : totalWorkers;
            const saturationPct =
              capacityBase > 0 ? Math.min(100, Math.round((renderingWorkers / capacityBase) * 100)) : 0;

            const badgeVariant = "outline" as const;
            let badgeText = "Idle";
            let badgeClass = "border-border text-muted-foreground bg-muted/20";
            let progressColor = "bg-primary";

            if (onlineWorkers === 0 && totalWorkers === 0) {
              badgeText = "Empty";
              badgeClass = "border-border text-muted-foreground bg-muted/10";
            } else if (onlineWorkers === 0) {
              badgeText = "Offline";
              badgeClass = "border-destructive/30 text-destructive bg-destructive/10";
            } else if (saturationPct >= 95) {
              badgeText = "100% Saturation";
              badgeClass = "border-amber-500/40 text-amber-500 bg-amber-500/10";
              progressColor = "bg-amber-500";
            } else if (saturationPct > 0) {
              badgeText = `${saturationPct}% Active`;
              badgeClass = "border-primary/40 text-primary bg-primary/10";
            }

            return (
              <div
                key={pool.id}
                className="p-3 rounded-lg border border-border/70 bg-card/60"
              >
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between gap-2">
                    <div className="truncate">
                      <p className="text-xs font-bold text-foreground truncate">{pool.name}</p>
                      <p className="text-xs text-muted-foreground truncate">
                        {pool.description || "General compute pool"}
                      </p>
                    </div>
                    <Badge variant={badgeVariant} className={`text-[11px] px-2 py-0.5 h-5 shrink-0 font-mono ${badgeClass}`}>
                      {badgeText}
                    </Badge>
                  </div>

                  <div className="space-y-1 pt-1">
                    <div className="flex items-center justify-between text-xs font-mono text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Cpu size={12} className="opacity-70" />
                        {renderingWorkers} / {onlineWorkers} rendering
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {totalWorkers} total
                      </span>
                    </div>
                    <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-muted/60">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${progressColor}`}
                        style={{ width: `${saturationPct}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
