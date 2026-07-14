import type { ReactNode } from "react";

export type DashboardView =
  | "Dashboard"
  | "Active Queue"
  | "Node Pool"
  | "AI Rules"
  | "Settings";

export interface SidebarItem {
  icon: ReactNode;
  label: DashboardView;
}

export type JobPriority = "HIGH" | "MED" | "LOW";
export type JobStatus = "Rendering" | "Simulating" | "Queued";

export interface RenderJob {
  id: string;
  priority: JobPriority;
  node: string;
  status: JobStatus;
  progress: number;
  eta: string;
  statusColor: string;
}

export type LogType = "INFO" | "ROUTE" | "WARN";

export interface LogEntry {
  time: string;
  type: LogType;
  msg: string;
  color: string;
}

export type LogMessage = Omit<LogEntry, "time">;

export interface TelemetryPoint {
  x: number;
  vram: number;
  cpu: number;
}
