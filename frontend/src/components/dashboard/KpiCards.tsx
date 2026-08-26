"use client";

import { AlertTriangle, ArrowUpRight, Cpu, Layers, Server, ShieldAlert, ShieldCheck, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";

interface KpiCardsProps {
  totalNodes: number;
  onlineNodes: number;
  totalCores: number;
  activeJobs: number;
  activeTasks: number;
  farmEfficiency: number;
  completedJobs: number;
  failedJobs: number;
  latencyMs: number | null;
  isOffline: boolean;
}

export default function KpiCards({
  totalNodes,
  onlineNodes,
  totalCores,
  activeJobs,
  activeTasks,
  farmEfficiency,
  completedJobs,
  failedJobs,
  latencyMs,
  isOffline,
}: KpiCardsProps) {
  let systemStatusText = "Operational";
  let systemStatusColor = "text-success";
  let SystemStatusIcon = ShieldCheck;

  if (isOffline) {
    systemStatusText = "Offline";
    systemStatusColor = "text-destructive";
    SystemStatusIcon = ShieldAlert;
  } else if (totalNodes > 0 && onlineNodes === 0 && activeJobs > 0) {
    systemStatusText = "No Workers";
    systemStatusColor = "text-warning";
    SystemStatusIcon = AlertTriangle;
  } else if (failedJobs > 0 && activeJobs === 0 && farmEfficiency < 75) {
    systemStatusText = "Attention";
    systemStatusColor = "text-warning";
    SystemStatusIcon = AlertTriangle;
  }

  return (
    <Card className="border-border p-0 rounded-none border-t-0 border-x-0 bg-background/50 backdrop-blur-md sticky top-0 z-10 shadow-sm shrink-0">
      <CardContent className="p-0">
        <div className="flex flex-wrap items-center justify-between px-4 h-12 text-sm font-mono overflow-x-auto no-scrollbar">
          
          <div className="flex items-center gap-6 text-xs whitespace-nowrap min-w-max pr-4">
            
            {/* Total Nodes */}
            <dl className="flex items-center gap-2">
              <dt className="text-muted-foreground font-semibold uppercase tracking-wider flex items-center gap-1">
                <Server size={12} className="opacity-50" />
                Nodes
              </dt>
              <dd className="font-bold flex items-center gap-1.5">
                <span className="text-foreground text-sm">{totalNodes}</span>
                <span className="text-muted-foreground/40 font-normal">/</span>
                {onlineNodes > 0 ? (
                  <span className="text-success">{onlineNodes} online</span>
                ) : (
                  <span className={totalNodes === 0 ? "text-muted-foreground" : "text-warning"}>
                    0 online
                  </span>
                )}
                {totalCores > 0 && (
                  <span className="text-muted-foreground opacity-60">({totalCores}c)</span>
                )}
              </dd>
            </dl>

            <div className="w-px h-5 bg-border/60" />

            {/* Active Jobs / Tasks */}
            <dl className="flex items-center gap-2">
              <dt className="text-muted-foreground font-semibold uppercase tracking-wider flex items-center gap-1">
                <Zap size={12} className="opacity-50 text-primary" />
                Active Work
              </dt>
              <dd className="font-bold flex items-center gap-1.5">
                <span className="text-foreground text-sm">{activeJobs}</span> <span className="text-muted-foreground font-normal">jobs</span>
                {activeTasks > 0 && (
                  <>
                    <span className="text-muted-foreground/40 font-normal">/</span>
                    <span className="text-primary">{activeTasks} tasks</span>
                  </>
                )}
              </dd>
            </dl>

            <div className="w-px h-5 bg-border/60" />

            {/* Farm Efficiency */}
            <dl className="flex items-center gap-2 w-48">
              <dt className="text-muted-foreground font-semibold uppercase tracking-wider">
                Efficiency
              </dt>
              <dd className="font-bold flex items-center gap-2 flex-1 w-full">
                <span className="text-foreground w-9 text-right text-sm">{farmEfficiency}%</span>
                <Progress value={farmEfficiency} className="h-1.5 flex-1" />
              </dd>
            </dl>
          </div>

          {/* System Status (Right aligned) */}
          <div className="flex items-center gap-2 text-xs min-w-max ml-auto pl-4 border-l border-border/60">
            <span className="text-muted-foreground">
              {isOffline ? "API Disconnected" : latencyMs !== null ? `${latencyMs}ms ping` : "..."}
            </span>
            <Badge variant="outline" className={`px-2 py-0.5 h-6 font-mono font-bold border-${systemStatusColor}/30 bg-${systemStatusColor}/5 ${systemStatusColor} gap-1.5`}>
              <SystemStatusIcon size={12} />
              {systemStatusText}
            </Badge>
          </div>

        </div>
      </CardContent>
    </Card>
  );
}
