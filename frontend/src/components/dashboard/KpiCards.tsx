"use client";

import { AlertTriangle, ArrowUpRight, Cpu, Layers, Server, ShieldAlert, ShieldCheck, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

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
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
      {/* 1. Total Nodes */}
      <Card>
        <CardHeader>
          <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center justify-between">
            <span>Total Nodes</span>
            <Server size={14} className="opacity-50" />
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          <p className="text-3xl font-bold tracking-tight text-foreground">{totalNodes}</p>
          <div className="text-xs font-mono flex items-center gap-1.5">
            {onlineNodes > 0 ? (
              <span className="text-success flex items-center gap-1 font-medium">
                <ArrowUpRight size={14} /> {onlineNodes} online
              </span>
            ) : totalNodes === 0 ? (
              <span className="text-muted-foreground">0 registered</span>
            ) : (
              <span className="text-warning flex items-center gap-1 font-medium">
                <AlertTriangle size={12} /> 0 online
              </span>
            )}
            {totalCores > 0 && (
              <span className="text-muted-foreground text-xs">
                &bull; {totalCores} cores
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* 2. Active Jobs */}
      <Card>
        <CardHeader>
          <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center justify-between">
            <span>Active Jobs</span>
            <Zap size={14} className="opacity-50 text-primary" />
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          <p className="text-3xl font-bold tracking-tight text-foreground">{activeJobs}</p>
          <p className="text-xs font-mono text-primary flex items-center gap-1.5">
            {activeTasks > 0 ? (
              <>
                <Layers size={13} /> {activeTasks} {activeTasks === 1 ? "task" : "tasks"} rendering
              </>
            ) : activeJobs > 0 ? (
              <>
                <Zap size={13} /> Processing
              </>
            ) : (
              <span className="text-muted-foreground">Queue idle</span>
            )}
          </p>
        </CardContent>
      </Card>

      {/* 3. Farm Efficiency */}
      <Card>
        <CardHeader>
          <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center justify-between">
            <span>Farm Efficiency</span>
            <span className="text-xs font-mono text-muted-foreground lowercase font-normal">
              {completedJobs} ok / {failedJobs} fail
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-3xl font-bold tracking-tight text-foreground">{farmEfficiency}%</p>
          <Progress value={farmEfficiency} className="h-1.5" />
        </CardContent>
      </Card>

      {/* 4. System Status */}
      <Card>
        <CardHeader>
          <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center justify-between">
            <span>Cluster Health</span>
            <Cpu size={14} className="opacity-50" />
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          <div className={`flex items-center gap-2 text-xl font-bold ${systemStatusColor}`}>
            <SystemStatusIcon size={20} />
            {systemStatusText}
          </div>
          <p className="text-xs font-mono text-muted-foreground">
            {isOffline
              ? "API Disconnected"
              : latencyMs !== null
              ? `Lat: ${latencyMs}ms / API: OK`
              : "Connecting..."}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
