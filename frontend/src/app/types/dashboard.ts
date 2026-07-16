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
export type BackendJobState =
  | "PENDING"
  | "RUNNING"
  | "FINISHED"
  | "FAILED"
  | "PAUSED";

export type JobStatus =
  | "Rendering"
  | "Queued"
  | "Completed"
  | "Failed";

export interface RenderJob {
  id: string;
  displayId: string;
  priority: JobPriority;
  node: string;
  status: JobStatus;
  backendState: BackendJobState;
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

export interface TelemetryMetrics {
  vramUsage: number;
  cpuLoad: number;
  points: TelemetryPoint[];
}
